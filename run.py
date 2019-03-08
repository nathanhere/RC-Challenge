from flask import Flask
from flask_cors import CORS
from app import api_bp  # This is referring to app.py


def create_app():
	app = Flask(__name__)
	CORS(app)
	app.register_blueprint(api_bp)  # url_prefix='/'specify a URL prefex like /api/ to segment it logically from other resources
	return app

app = create_app()

if __name__ == "__main__":
	app.run(host='0.0.0.0')  # debug=True)
