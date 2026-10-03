// Package tailcatbridge exposes a tiny Android-bindable surface over Tailcat.
// It intentionally hides Tailcat's unstable Go API from the Java application.
package tailcatbridge

import (
	"context"
	"fmt"
	"net"
	"sync"
	"time"

	"github.com/tailscale/tailcat"
)

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
// It returns the chosen localhost port.
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

	// Prove that the Tailcat path can actually reach the receiver before
	// returning success to Android. This avoids reporting a local listener as
	// "connected" when DERP/DNS/path bootstrap has already failed.
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
