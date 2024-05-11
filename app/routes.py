from flask import Blueprint, render_template, request
import run
import os

bp = Blueprint('main', __name__)


@bp.route('/', methods=['GET', 'POST'])
def index():

    subdomains = []
    if os.path.exists("results/" + run.domain + "/subdomains.txt"):
        with open("results/" + run.domain + "/subdomains.txt", 'r') as file:
            subdomains = file.readlines()

    return render_template('index.html', subdomains=subdomains)