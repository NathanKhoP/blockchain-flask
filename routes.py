import json
from urllib import error, request as urlrequest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import jsonify, request


def register_routes(app, blockchain):
    @app.route('/get_chain', methods=['GET'])
    def get_chain():
        response = {
            'chain': blockchain.chain,
            'length': len(blockchain.chain),
        }
        return jsonify(response), 200

    @app.route('/mining', methods=['GET'])
    def mining():
        miner_address = request.args.get('miner', 'miner_address')
        prev_block = blockchain.get_last_block()
        prev_proof = prev_block['proof']
        proof, proof_of_work = blockchain.proof_of_work(prev_proof)
        prev_hash = prev_block['hash']

        reward_tx = {
            'sender': 'SYSTEM',
            'recipient': miner_address,
            'amount': 10,
            'signature': '',
            'sender_public_key': '',
        }

        txs_to_mine = list(blockchain.pending_transactions)
        txs_to_mine.append(reward_tx)

        created_block = blockchain.create_block(proof, prev_hash, proof_of_work, txs_to_mine)
        blockchain.pending_transactions = []
        blockchain.broadcast_json('/blocks/receive', {'block': created_block})

        response = {
            'message': 'Block mined successfully',
            'created block': created_block,
            'pending_count': len(blockchain.pending_transactions),
        }
        return jsonify(response), 200

    @app.route('/transactions/pending', methods=['GET'])
    def get_pending_transactions():
        response = {
            'pending_transactions': blockchain.pending_transactions,
            'length': len(blockchain.pending_transactions),
        }
        return jsonify(response), 200

    @app.route('/wallet/new', methods=['GET'])
    def create_wallet():
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        response = {
            'private_key': private_bytes.hex(),
            'public_key': public_bytes.hex(),
            'address': public_bytes.hex(),
        }
        return jsonify(response), 200

    @app.route('/transactions/sign', methods=['POST'])
    def sign_transaction():
        data = request.get_json(silent=True) or {}
        required = {'private_key', 'sender', 'recipient', 'amount'}
        if not required.issubset(data.keys()):
            return jsonify({'message': 'Missing transaction signing fields'}), 400

        try:
            amount = int(data['amount'])
            private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(data['private_key']))
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid private key or amount'}), 400

        payload = blockchain.make_transaction_payload(data['sender'], data['recipient'], amount)
        signature = private_key.sign(payload).hex()

        response = {
            'sender': data['sender'],
            'recipient': data['recipient'],
            'amount': amount,
            'sender_public_key': data['sender'],
            'signature': signature,
        }
        return jsonify(response), 200

    @app.route('/transactions/new', methods=['POST'])
    def add_transaction():
        data = request.get_json(silent=True) or {}

        is_added, message = blockchain.add_transaction(data)
        if not is_added:
            return jsonify({'message': message}), 400

        blockchain.broadcast_json('/transactions/receive', {'transaction': data})
        response = {
            'message': message,
            'pending_count': len(blockchain.pending_transactions),
        }
        return jsonify(response), 201

    @app.route('/transactions/receive', methods=['POST'])
    def receive_transaction():
        data = request.get_json(silent=True) or {}
        tx = data.get('transaction')
        if tx is None:
            return jsonify({'message': 'Missing transaction payload'}), 400

        for existing_tx in blockchain.pending_transactions:
            if existing_tx == tx:
                return jsonify({'message': 'Transaction already pending'}), 200

        is_added, message = blockchain.add_transaction(tx)
        status = 200 if is_added else 400
        return jsonify({'message': message}), status

    @app.route('/faucet', methods=['POST'])
    def faucet():
        data = request.get_json(silent=True) or {}
        address = data.get('address')
        amount = data.get('amount', 100)
        if not address:
            return jsonify({'message': 'Address is required'}), 400

        try:
            amount = int(amount)
        except (TypeError, ValueError):
            return jsonify({'message': 'Amount must be an integer'}), 400

        if amount <= 0:
            return jsonify({'message': 'Amount must be greater than zero'}), 400

        tx = blockchain.add_system_transaction(address, amount)
        blockchain.broadcast_json('/transactions/receive', {'transaction': tx})
        return jsonify({'message': 'Faucet transaction added', 'transaction': tx}), 201

    @app.route('/is_valid', methods=['GET'])
    def is_valid():
        chain_valid = blockchain.is_chain_valid()
        if chain_valid:
            response = {
                'message': 'Blockchain is valid',
            }
        else:
            response = {
                'message': 'Blockchain is not valid',
            }
        return jsonify(response), 200

    @app.route('/balance/<address>', methods=['GET'])
    def get_balance(address):
        response = {
            'address': address,
            'balance': blockchain.get_balance(address),
        }
        return jsonify(response), 200

    @app.route('/nodes/register', methods=['POST'])
    def register_nodes():
        data = request.get_json(silent=True) or {}
        nodes = data.get('nodes', [])
        if not nodes:
            return jsonify({'message': 'Provide at least one node'}), 400

        for node in nodes:
            blockchain.register_node(node)

        response = {
            'message': 'Nodes registered successfully',
            'total_nodes': sorted(blockchain.nodes),
        }
        return jsonify(response), 201

    @app.route('/nodes', methods=['GET'])
    def list_nodes():
        response = {
            'nodes': sorted(blockchain.nodes),
            'length': len(blockchain.nodes),
        }
        return jsonify(response), 200

    @app.route('/blocks/receive', methods=['POST'])
    def receive_block():
        data = request.get_json(silent=True) or {}
        block = data.get('block')
        if block is None:
            return jsonify({'message': 'Missing block payload'}), 400

        for existing_block in blockchain.chain:
            if existing_block.get('hash') == block.get('hash'):
                return jsonify({'message': 'Block already exists'}), 200

        if not blockchain.is_new_block_valid(block):
            return jsonify({'message': 'Invalid block'}), 400

        blockchain.chain.append(block)
        mined_txs = block.get('transactions', [])
        blockchain.pending_transactions = [
            tx for tx in blockchain.pending_transactions if tx not in mined_txs
        ]
        return jsonify({'message': 'Block added'}), 201

    @app.route('/nodes/resolve', methods=['GET'])
    def resolve_nodes():
        replaced = False
        for node in blockchain.nodes:
            try:
                with urlrequest.urlopen(f"{node}/get_chain", timeout=3) as response:
                    data = json.loads(response.read().decode('utf-8'))
            except (error.URLError, error.HTTPError, json.JSONDecodeError):
                continue

            node_chain = data.get('chain')
            if not isinstance(node_chain, list):
                continue
            if blockchain.replace_chain(node_chain):
                replaced = True

        if replaced:
            response = {
                'message': 'Chain replaced by longest valid chain',
                'new_length': len(blockchain.chain),
            }
        else:
            response = {
                'message': 'Current chain is authoritative',
                'length': len(blockchain.chain),
            }
        return jsonify(response), 200
