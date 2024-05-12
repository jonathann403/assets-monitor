from flask import Blueprint, render_template, request
import json
import os

bp = Blueprint('main', __name__)

@bp.route('/', methods=['GET', 'POST'])
def index():
    domain = request.args.get('domain')  # Get the value of 'domain' from the query string
    domains = [f.path.split("./results/")[1] for f in os.scandir("./results/") if f.is_dir()]

    if domain:
        httpx_json_path = f"results/{domain}/httpx.json"

        if os.path.exists(httpx_json_path):
            with open(httpx_json_path, 'r') as file:
                try:
                    data = json.load(file)
                except Exception as e:
                    return render_template('index.html', data=False, domains=domains)

            return render_template('index.html', data=data, domains=domains)

        else:
            # Handle the case when neither file exists for the specified domain
            return render_template('index.html', data=False, domains=domains)

    else:
        return render_template('index.html', data=False, domains=domains)
