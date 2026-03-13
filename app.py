import os

from flask import Flask

from blockchain import Blockchain
from routes import register_routes


app = Flask(__name__)
blockchain = Blockchain()
register_routes(app, blockchain)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')))
