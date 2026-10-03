// Package tailcatbridge exposes a tiny Android-bindable surface over Tailcat.
// It intentionally hides Tailcat's unstable Go API from the Java application.
package tailcatbridge

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/netip"
	"slices"
	"strings"
	"sync"
	"time"

	"github.com/tailscale/tailcat"
	"tailscale.com/net/netmon"
)

// InterfaceLister is implemented by Android through gomobile reverse bindings.
// Android app UIDs cannot reliably use Go's net.Interfaces on API 30+, so the
// host app enumerates interfaces through java.net.NetworkInterface instead.
type InterfaceLister interface {
	InterfacesAsJson() (string, error)
}

// SetInterfaceLister installs Android's Java-side interface enumerator into
// Tailscale netmon. It must be called before the first Tailcat client is built.
func SetInterfaceLister(l InterfaceLister) {
	if l == nil {
		return
	}
	netmon.RegisterInterfaceGetter(func() ([]netmon.Interface, error) {
		return interfacesFromLister(l)
	})
}

// SetDefaultRouteInterface gives netmon the active interface name when the host
// knows it. Empty is accepted and simply means "unknown".
func SetDefaultRouteInterface(name string) {
	netmon.UpdateLastKnownDefaultRouteInterface(strings.TrimSpace(name))
}

type listerAddr struct {
	IP        string `json:"ip"`
	PrefixLen int    `json:"prefixLen"`
}

type listerInterface struct {
	Name         string       `json:"name"`
	Index        int          `json:"index"`
	MTU          int          `json:"mtu"`
	Up           bool         `json:"up"`
	Broadcast    bool         `json:"broadcast"`
	Loopback     bool         `json:"loopback"`
	PointToPoint bool         `json:"pointToPoint"`
	Multicast    bool         `json:"multicast"`
	Addrs        []listerAddr `json:"addrs"`
}

func interfacesFromLister(l InterfaceLister) ([]netmon.Interface, error) {
	payload, err := l.InterfacesAsJson()
	if err != nil {
		return nil, fmt.Errorf("host interface lister failed: %w", err)
	}
	payload = strings.TrimSpace(payload)
	if payload == "" {
		return nil, errors.New("host interface lister returned empty payload")
	}
	var raw []listerInterface
	if err := json.Unmarshal([]byte(payload), &raw); err != nil {
		return nil, fmt.Errorf("host interface lister payload malformed: %w", err)
	}
	out := make([]netmon.Interface, 0, len(raw))
	for i, in := range raw {
		if in.Name == "" {
			return nil, fmt.Errorf("host interface lister entry %d has no name", i)
		}
		iface := netmon.Interface{
			Interface: &net.Interface{Name: in.Name, Index: in.Index, MTU: in.MTU},
			// Non-nil AltAddrs is mandatory. Nil would make netmon fall back to
			// net.Interface.Addrs(), which is the forbidden netlink path.
			AltAddrs: []net.Addr{},
		}
		if in.Up {
			iface.Flags |= net.FlagUp
		}
		if in.Broadcast {
			iface.Flags |= net.FlagBroadcast
		}
		if in.Loopback {
			iface.Flags |= net.FlagLoopback
		}
		if in.PointToPoint {
			iface.Flags |= net.FlagPointToPoint
		}
		if in.Multicast {
			iface.Flags |= net.FlagMulticast
		}
		for _, a := range in.Addrs {
			addr, err := a.netAddr()
			if err != nil {
				return nil, fmt.Errorf("interface %s: %w", in.Name, err)
			}
			iface.AltAddrs = append(iface.AltAddrs, addr)
		}
		out = append(out, iface)
	}
	if len(out) == 0 {
		return nil, errors.New("host interface lister returned no interfaces")
	}
	return out, nil
}

func (a listerAddr) netAddr() (net.Addr, error) {
	ip, err := netip.ParseAddr(a.IP)
	if err != nil {
		return nil, fmt.Errorf("address %q: %w", a.IP, err)
	}
	raw := net.IP(slices.Clone(ip.AsSlice()))
	if zone := ip.Zone(); zone != "" {
		return &net.IPAddr{IP: raw, Zone: zone}, nil
	}
	bits := ip.BitLen()
	if a.PrefixLen < 0 || a.PrefixLen > bits {
		return nil, fmt.Errorf("address %s prefix %d outside /0../%d", a.IP, a.PrefixLen, bits)
	}
	return &net.IPNet{IP: raw, Mask: net.CIDRMask(a.PrefixLen, bits)}, nil
}

type forwarder struct {
	cancel context.CancelFunc
	ln     net.Listener
	client *tailcat.Client
}

var (
	mu      sync.Mutex
	current *forwarder
)

// StartForward starts one localhost TCP listener and forwards accepted
// connections to remotePort on the Tailcat server described by address.
// It probes the Tailcat path first, so success means the remote receiver port
// was actually reachable.
func StartForward(address string, remotePort int) (int, error) {
	if remotePort < 1 || remotePort > 65535 {
		return 0, fmt.Errorf("invalid remote port")
	}
	if len(address) < 20 || len(address) > 4096 {
		return 0, fmt.Errorf("invalid tailcat address")
	}

	mu.Lock()
	defer mu.Unlock()
	stopLocked()

	ctx, cancel := context.WithCancel(context.Background())
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		cancel()
		return 0, fmt.Errorf("listen localhost: %w", err)
	}
	cl := tailcat.NewClient(tailcat.Addr(address))

	probeCtx, probeCancel := context.WithTimeout(ctx, 15*time.Second)
	probe, err := cl.DialTCPPort(probeCtx, uint16(remotePort))
	probeCancel()
	if err != nil {
		_ = ln.Close()
		_ = cl.Close()
		cancel()
		return 0, fmt.Errorf("tailcat dial receiver: %w", err)
	}
	_ = probe.Close()

	f := &forwarder{cancel: cancel, ln: ln, client: cl}
	current = f
	go f.acceptLoop(ctx, uint16(remotePort))

	tcp, ok := ln.Addr().(*net.TCPAddr)
	if !ok || tcp.Port <= 0 {
		stopLocked()
		return 0, fmt.Errorf("invalid localhost listener")
	}
	return tcp.Port, nil
}

// StopForward stops the active forwarding listener and Tailcat client.
func StopForward() {
	mu.Lock()
	defer mu.Unlock()
	stopLocked()
}

func stopLocked() {
	if current == nil {
		return
	}
	current.cancel()
	_ = current.ln.Close()
	_ = current.client.Close()
	current = nil
}

func (f *forwarder) acceptLoop(ctx context.Context, remotePort uint16) {
	for {
		local, err := f.ln.Accept()
		if err != nil {
			return
		}
		go f.proxyOne(ctx, local, remotePort)
	}
}

func (f *forwarder) proxyOne(ctx context.Context, local net.Conn, remotePort uint16) {
	defer local.Close()
	remote, err := f.client.DialTCPPort(ctx, remotePort)
	if err != nil {
		return
	}
	defer remote.Close()
	tailcat.ProxyConns(local, remote)
}
