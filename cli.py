#!/usr/bin/env python3
import argparse
import json
import sys
from urllib import error, parse, request


def call_endpoint(base_url, endpoint, method="GET", data=None, json_data=None, timeout=10):
    url = f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    payload = None
    headers = {}

    if json_data is not None:
        payload = json.dumps(json_data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None:
        payload = parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = request.Request(url, data=payload, method=method, headers=headers)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            status = resp.getcode()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error {exc.code} while calling {url}", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        return 1
    except error.URLError as exc:
        print(f"Connection error while calling {url}: {exc}", file=sys.stderr)
        return 1

    try:
        parsed = json.loads(body)
        print(json.dumps(parsed, indent=2, ensure_ascii=True))
    except json.JSONDecodeError:
        print(body)

    return 0 if status < 400 else 1


def build_parser():
    parser = argparse.ArgumentParser(
        description="CLI client for blockchain Flask endpoints"
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5000",
        help="Base URL of the blockchain API (default: http://127.0.0.1:5000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Request timeout in seconds (default: 10)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("get-chain", help="GET /get_chain")
    mine_parser = subparsers.add_parser("mine", help="GET /mining")
    mine_parser.add_argument(
        "--miner",
        default="miner_address",
        help="Miner address to receive block reward",
    )
    subparsers.add_parser("is-valid", help="GET /is_valid")
    subparsers.add_parser("pending", help="GET /transactions/pending")
    subparsers.add_parser("new-wallet", help="GET /wallet/new")
    subparsers.add_parser("list-nodes", help="GET /nodes")
    subparsers.add_parser("resolve", help="GET /nodes/resolve")

    balance_parser = subparsers.add_parser("balance", help="GET /balance/<address>")
    balance_parser.add_argument("--address", required=True, help="Wallet address")

    sign_parser = subparsers.add_parser("sign", help="POST /transactions/sign")
    sign_parser.add_argument("--private-key", required=True, help="Sender private key (hex)")
    sign_parser.add_argument("--sender", required=True, help="Sender address/public key")
    sign_parser.add_argument("--recipient", required=True, help="Recipient address")
    sign_parser.add_argument("--amount", required=True, type=int, help="Amount in coins")

    tx_parser = subparsers.add_parser(
        "tx", help="POST /transactions/new (requires signature from sign command)"
    )
    tx_parser.add_argument("--sender", required=True, help="Sender address/public key")
    tx_parser.add_argument("--recipient", required=True, help="Recipient address")
    tx_parser.add_argument("--amount", required=True, type=int, help="Amount in coins")
    tx_parser.add_argument("--signature", required=True, help="Signature hex")
    tx_parser.add_argument(
        "--sender-public-key",
        required=True,
        help="Sender public key hex (same as sender address)",
    )

    faucet_parser = subparsers.add_parser("faucet", help="POST /faucet")
    faucet_parser.add_argument("--address", required=True, help="Recipient address")
    faucet_parser.add_argument("--amount", type=int, default=100, help="Faucet amount")

    register_parser = subparsers.add_parser("register-nodes", help="POST /nodes/register")
    register_parser.add_argument(
        "--node",
        action="append",
        required=True,
        help="Node URL, can be passed multiple times",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "get-chain":
        return call_endpoint(args.base_url, "/get_chain", timeout=args.timeout)

    if args.command == "mine":
        miner_q = parse.urlencode({"miner": args.miner})
        return call_endpoint(args.base_url, f"/mining?{miner_q}", timeout=args.timeout)

    if args.command == "is-valid":
        return call_endpoint(args.base_url, "/is_valid", timeout=args.timeout)

    if args.command == "pending":
        return call_endpoint(args.base_url, "/transactions/pending", timeout=args.timeout)

    if args.command == "new-wallet":
        return call_endpoint(args.base_url, "/wallet/new", timeout=args.timeout)

    if args.command == "list-nodes":
        return call_endpoint(args.base_url, "/nodes", timeout=args.timeout)

    if args.command == "resolve":
        return call_endpoint(args.base_url, "/nodes/resolve", timeout=args.timeout)

    if args.command == "balance":
        return call_endpoint(args.base_url, f"/balance/{args.address}", timeout=args.timeout)

    if args.command == "sign":
        return call_endpoint(
            args.base_url,
            "/transactions/sign",
            method="POST",
            json_data={
                "private_key": args.private_key,
                "sender": args.sender,
                "recipient": args.recipient,
                "amount": args.amount,
            },
            timeout=args.timeout,
        )

    if args.command == "tx":
        return call_endpoint(
            args.base_url,
            "/transactions/new",
            method="POST",
            json_data={
                "sender": args.sender,
                "recipient": args.recipient,
                "amount": args.amount,
                "signature": args.signature,
                "sender_public_key": args.sender_public_key,
            },
            timeout=args.timeout,
        )

    if args.command == "faucet":
        return call_endpoint(
            args.base_url,
            "/faucet",
            method="POST",
            json_data={"address": args.address, "amount": args.amount},
            timeout=args.timeout,
        )

    if args.command == "register-nodes":
        return call_endpoint(
            args.base_url,
            "/nodes/register",
            method="POST",
            json_data={"nodes": args.node},
            timeout=args.timeout,
        )

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
