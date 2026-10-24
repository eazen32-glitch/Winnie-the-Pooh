"""Run the isolated section without the rest of NextStep."""
import argparse
from flask import Flask
from skills_radar import init_app

def create_app(auto_refresh=False):
    app = Flask(__name__)
    init_app(app, auto_refresh=auto_refresh)
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Enable original public-source refresh every 15 minutes')
    parser.add_argument('--port', type=int, default=5051)
    args = parser.parse_args()
    create_app(args.live).run(host='127.0.0.1', port=args.port, debug=False)
