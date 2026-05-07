#!/usr/bin/env python3
import argparse
import os
import socket
import struct
import sys
from typing import Tuple

#############
# Constants #
#############
DEFAULT_PORT = 9090
DEFAULT_IPV4_ADDRESS = '127.0.0.1'
DEFAULT_IPV6_ADDRESS = '::1'
DEFAULT_OUTDIR = './'
BUFSIZE = 64 * 1024
MAX_FILENAME_LEN = 4096

LINE_OK = b'OK\n'
LINE_ERR = b'ERR\n'

###############
# I/O helpers #
###############

def recv_line(sock: socket.socket, max_len: int = MAX_FILENAME_LEN) -> bytes:
    """Receive a single line terminated by '\n'.
    Returns the line including everything before '\n' (without '\n').
    Raises a ValueError if more data than max_len is received.
    """
    while True:
        ch = sock.recv(1)
        if not ch:
            raise ConnectionError("Connection is closed before new line")
        if ch == b'\n':
            return bytes(data)
        data += ch
        if len(data) > max_len:
            raise ValueError("The line is too long")
            #if the length of data is greater than the maximum length then raise an error that the line is too long

##########
# Server #
##########

def handle_client(conn: socket.socket, outdir: str) -> None:
    """Handle a single client:
    1) Read filepath and sanitise it.
    2) Check existence of <outdir>/<filename>-received
    3) Reply LINE_OK/LINE_ERR accordingly
    4) If LINE_OK, receive length and payload, write file, and send final LINE_OK.
    On any error, send LINE_ERR and return.
    """
    try:
        # Receive filename line (UTF-8).
        raw_line = recv_line(conn)
        try:
            filename = raw_line.decode('utf-8')
        except UnicodeDecodeError:
            # Send LINE_ERR if filename is not valid UTF-8.
            conn.sendall(LINE_ERR)
            return

        # Sanitize filename (strip directory components).
        filename = os.path.basename(filename)
        if filename == '':
            # Send LINE_ERR if invalid filename.
            conn.sendall(LINE_ERR)
            return

        # Prepare output path.
        os.makedirs(outdir, exist_ok=True)
        dest_path = os.path.join(outdir, f"{filename}-received")

        # Check if file already exists.
        if os.path.exists(dest_path):
            # Send LINE_ERR if file exists.
            conn.sendall(LINE_ERR)
            return
        else:
            # Send LINE_OK to proceed.
            conn.sendall(LINE_OK)

        # Receive 8-byte unsigned integer (network byte order).
        hdr = bytearray()
        while len(hdr) < 8:
            chunk = conn.recv(8 - len(hdr))
            if not chunk:
                raise ConnectionError("connection closed while receiving file data")
            
        
        conn.sendall(LINE_OK)

        (file_size,) = struct.unpack('!Q', hdr)

        # Receive exactly file_size bytes and write to destination.
        remaining = file_size
        try:
            with open(dest_path, 'wb') as f:
                while remaining > 0:
                    # Receive a chunk (up to BUFSIZE or remaining).
                    chunk = conn.recv(min(BUFSIZE, remaining))
                    if not chunk:
                    f.write(chunk)
                    remaining -= len(chunk)
                f.flush()
        except Exception:
            # On failure, try to remove partial file.
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                pass
            raise

        # Send final LINE_OK to acknowledge successful receipt.
        conn.sendall(LINE_OK)

    except Exception:
        # Swallow exceptions to keep server alive; optionally could log
        try:
            # Best-effort negative acknowledgement if we failed before final OK
            pass
        except Exception:
            pass
        return


def run_server(port: int, outdir: str, ipv6: bool) -> None:
    """Start the TCP file transfer server."""
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    bind_addr = '::' if ipv6 else '0.0.0.0'
    # Create server socket, bind, listen, and accept in an infinite loop.
    with socket.socket(family, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if ipv6:
            try:
                srv.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            except OSError:
                pass
        srv.bind((bind_addr, port))
        srv.listen(1)

        while True:
            conn, _addr = srv.accept()
            with conn:
                handle_client(conn, outdir)







##########
# Client #
##########

def run_client(server_ip: str, port: int, file_path: str, ipv6: bool) -> int:
    """Establish connection to server and send the specified file."""
    # Resolve filename and size.
    if not os.path.isfile(file_path):
        print(f"Not a file: {file_path}", file=sys.stderr)
        return 2
    filename = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    addr = (server_ip, port, 0, 0) if ipv6 else (server_ip, port)

    # Send filename, size, and file content (in chunks).
    # Wait for server responses according to protocol.
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.connect(addr)

            sock.sendall(filename.encode('utf-8') + b'\n')

            reply = recv_line(sock)
            if reply == b'ERR':
                return 1
            if reply != b'OK':
                return 255
            
            sock.sendall(struct.pack('!Q', file_size))

            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(BUFSIZE)
                    if not chunk:
                        break
                    sock.sendall(chunk)

            final_reply = recv_line(sock)
            if final_reply == b'OK':
                return 0
            if final_reply == b'ERR':
                return 1
            return 255

    except Exception:
        return 255


################
# Main program #
################

def parse_args(argv=None) -> argparse.Namespace:
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description='TCP file transfer (client/server)')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--server', action='store_true', help='Run in server mode')
    mode.add_argument('--client', action='store_true', help='Run in client mode (default)')

    p.add_argument('--port', type=int, default=DEFAULT_PORT, help='TCP port (default: 9090)')
    p.add_argument('--outdir', default=DEFAULT_OUTDIR, help='Server: output directory (default: ./)')
    p.add_argument('--connect', dest='server_ip', default=None,
                   help='Client: server IPv4/IPv6 address (default: 127.0.0.1 or ::1 with --ipv6).')
    p.add_argument('--file', dest='file_path', help='Client: path to the file to send (no default).')
    p.add_argument('--ipv6', action='store_true', help='Use IPv6 sockets.')
    return p.parse_args(argv)

def main(argv=None) -> int:
    """Main program entry point."""

    args = parse_args(argv)

    # Run in server mode if --server is specified.
    if args.server:
        outdir = args.outdir
        run_server(args.port, outdir, ipv6=args.ipv6)
        return 0

    # Default to client if neither --server nor --client are specified.
    server_ip = args.server_ip
    if server_ip is None:
        server_ip = DEFAULT_IPV6_ADDRESS if args.ipv6 else DEFAULT_IPV4_ADDRESS

    if not args.file_path:
        print('Client mode requires --file <path>', file=sys.stderr)
        return 2

    rc = run_client(server_ip, args.port, args.file_path, ipv6=args.ipv6)
    return rc

if __name__ == '__main__':
    sys.exit(main())
