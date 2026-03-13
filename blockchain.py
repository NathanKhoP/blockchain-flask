import datetime
import hashlib
import json
from urllib import error, request as urlrequest

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.nodes = set()
        # genesis block
        self.create_block(proof=1, prev_hash='0', proof_of_work='genesis', transactions=[])

    def create_block(self, proof, prev_hash, proof_of_work, transactions):
        block = {
            'id_block': len(self.chain) + 1,
            'timestamp': str(datetime.datetime.now()),
            'proof': proof,
            'prev_hash': prev_hash,
            'proof_of_work': proof_of_work,
            'transactions': transactions,
        }
        block['hash'] = self.get_hash(block)
        self.chain.append(block)
        return block

    def get_last_block(self):
        return self.chain[-1]

    def proof_of_work(self, prev_proof):
        new_proof = 1
        check_proof = False
        while check_proof is False:
            hash_operation = hashlib.sha256(str(new_proof**2 - prev_proof**2).encode()).hexdigest()
            if hash_operation[:4] == '0000':
                check_proof = True
            else:
                new_proof += 1
        return new_proof, hash_operation

    def get_hash(self, block):
        block_data = dict(block)
        block_data.pop('hash', None)
        hash_operation = hashlib.sha256(json.dumps(block_data, sort_keys=True).encode()).hexdigest()
        return hash_operation

    def register_node(self, node_address):
        node = node_address.strip().rstrip('/')
        if not node:
            return False
        if not node.startswith('http://') and not node.startswith('https://'):
            node = f'http://{node}'
        self.nodes.add(node)
        return True

    def make_transaction_payload(self, sender, recipient, amount):
        return f"{sender}|{recipient}|{amount}".encode('utf-8')

    def verify_transaction_signature(self, transaction):
        sender = transaction.get('sender')
        if sender == 'SYSTEM':
            return True

        signature = transaction.get('signature')
        sender_public_key = transaction.get('sender_public_key')
        recipient = transaction.get('recipient')
        amount = transaction.get('amount')

        if not signature or not sender_public_key or recipient is None or amount is None:
            return False

        if sender_public_key != sender:
            return False

        try:
            public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(sender_public_key))
            payload = self.make_transaction_payload(sender, recipient, amount)
            public_key.verify(bytes.fromhex(signature), payload)
        except (ValueError, InvalidSignature):
            return False

        return True

    def get_balance(self, address):
        balance = 0
        for block in self.chain:
            for tx in block['transactions']:
                if tx['recipient'] == address:
                    balance += tx['amount']
                if tx['sender'] == address:
                    balance -= tx['amount']
        for tx in self.pending_transactions:
            if tx['sender'] == address:
                balance -= tx['amount']
        return balance

    def validate_transaction(self, transaction):
        required_fields = {'sender', 'recipient', 'amount', 'signature', 'sender_public_key'}
        if not required_fields.issubset(transaction.keys()):
            return False, 'Missing transaction fields'

        try:
            amount = int(transaction['amount'])
        except (TypeError, ValueError):
            return False, 'Amount must be an integer'

        if amount <= 0:
            return False, 'Amount must be greater than zero'

        transaction['amount'] = amount

        if not self.verify_transaction_signature(transaction):
            return False, 'Invalid digital signature'

        sender = transaction['sender']
        if self.get_balance(sender) < amount:
            return False, 'Insufficient balance'

        return True, ''

    def add_transaction(self, transaction):
        is_valid, message = self.validate_transaction(transaction)
        if not is_valid:
            return False, message

        self.pending_transactions.append(transaction)
        return True, 'Transaction added to pending list'

    def add_system_transaction(self, recipient, amount):
        tx = {
            'sender': 'SYSTEM',
            'recipient': recipient,
            'amount': int(amount),
            'signature': '',
            'sender_public_key': '',
        }
        self.pending_transactions.append(tx)
        return tx

    def broadcast_json(self, endpoint, payload):
        for node in self.nodes:
            url = f"{node}{endpoint}"
            req = urlrequest.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST',
            )
            try:
                urlrequest.urlopen(req, timeout=2)
            except (error.URLError, error.HTTPError):
                continue

    def is_chain_valid(self):
        if not self.chain:
            return False

        prev_block = self.chain[0]
        if prev_block['prev_hash'] != '0':
            return False

        if prev_block.get('hash') != self.get_hash(prev_block):
            return False

        now_index = 1
        while now_index < len(self.chain):
            now_block = self.chain[now_index]

            # 1. check if hash now block = prev hash
            prev_hash = prev_block['hash']
            if prev_hash != now_block['prev_hash']:
                return False

            # 2. check if proof of work is valid
            now_proof = now_block['proof']
            prev_proof = prev_block['proof']
            hash_operation = hashlib.sha256(str(now_proof**2 - prev_proof**2).encode()).hexdigest()
            if hash_operation[:4] != '0000':
                return False

            if now_block['proof_of_work'] != hash_operation:
                return False

            if now_block.get('hash') != self.get_hash(now_block):
                return False

            for tx in now_block.get('transactions', []):
                if tx['sender'] == 'SYSTEM':
                    continue
                if not self.verify_transaction_signature(tx):
                    return False

            prev_block = now_block
            now_index += 1
        return True

    def is_new_block_valid(self, block):
        last_block = self.get_last_block()
        if block['prev_hash'] != last_block['hash']:
            return False

        hash_operation = hashlib.sha256(
            str(block['proof']**2 - last_block['proof']**2).encode()
        ).hexdigest()
        if hash_operation[:4] != '0000':
            return False

        if block['proof_of_work'] != hash_operation:
            return False

        if block.get('hash') != self.get_hash(block):
            return False

        for tx in block.get('transactions', []):
            if tx['sender'] == 'SYSTEM':
                continue
            if not self.verify_transaction_signature(tx):
                return False

        return True

    def replace_chain(self, new_chain):
        current_length = len(self.chain)
        new_length = len(new_chain)
        if new_length <= current_length:
            return False

        old_chain = self.chain
        self.chain = new_chain
        if not self.is_chain_valid():
            self.chain = old_chain
            return False
        return True
