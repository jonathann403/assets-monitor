from flask import Blueprint, render_template, request
import json
import run
import os

bp = Blueprint('main', __name__)


@bp.route('/', methods=['GET', 'POST'])
def index():

    subdomains = []
    if os.path.exists("results/" + run.domain + "/httpx.json"):
        with open("results/" + run.domain + "/httpx.json", 'r') as file:
            data = json.load(file)

        return render_template('index.html', data=data, subdomains=False)

    elif os.path.exists("results/" + run.domain + "/subdomains.txt"):
        with open("results/" + run.domain + "/subdomains.txt", 'r') as file:
            subdomains = file.readlines()

        return render_template('index.html', subdomains=subdomains, data=False)