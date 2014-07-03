#!/usr/bin/env python

from cStringIO import StringIO
from configobj import ConfigObj
from flask import Flask
from flask import abort
from flask import redirect
from flask import render_template
from flask import request
from os import path
from requests import get
from requests import post
from requests.auth import HTTPBasicAuth
from urllib import urlencode

## Web Application Helpers ##
def configure():
    config_fp = '/etc/arkform.conf'
    if __name__ == '__main__':
        config_fp = path.join(project_dir(), 'etc/arkform.conf')

    config = ConfigObj(config_fp)

    # Remove trailing '/'s if they're there.
    if config['cas']['url'][-1:] == '/':
        config['cas']['url'] = config['cas']['url'][:-1]
    if config['ezid']['service'][-1:] == '/':
        config['ezid']['service'] = config['ezid']['service'][:-1]
    if config['ezid']['resolver'][-1:] == '/':
        config['ezid']['resolver'] = config['ezid']['resolver'][:-1]
    return config

def project_dir():
    return path.dirname(path.dirname(path.realpath(__file__)))

def cas_validate(request, cas_url):
    params = { 'service' : request.base_url,'ticket' : request.form['ticket'] }
    validate_url = "%s/validate" % (cas_url,)
    resp = get(validate_url, params=params)
    body = StringIO(resp.content).readlines()
    if body[0].strip() == 'yes':
        return body[1].strip()
    else:
        return None

def modify(config, ark, target_url=None):
    body = '_target:%s\nwho:%s' % (target_url,config["who"])
    if target_url in ('', None):
        body += '\n_status:unavailable | withdrawn'
    url = '%s/id/%s' % (config['service'], ark)
    auth = HTTPBasicAuth(config['user'], config['password'])
    headers = { 'content-type' : 'text/plain' }
    resp = post(url, auth=auth, data=body, headers=headers)
    if resp.status_code == 200:
        return '%s/%s' % (config['resolver'], ark)
    else:
        raise Exception(resp.content)

def mint_and_bind(config, target_url):
    body = '_target:%s\nerc:who:%s' % (target_url,config["who"])
    url = '%s/shoulder/%s' % (config['service'], config['shoulder'])
    auth = HTTPBasicAuth(config['user'], config['password'])
    headers = { 'content-type' : 'text/plain' }
    resp = post(url, auth=auth, data=body, headers=headers)
    if resp.status_code == 201:
        ark = resp.content.split(': ')[1].strip()
        return '%s/%s' % (config['resolver'], ark)
    else:
        raise Exception(resp.content)

### Web Application ###
app = Flask(__name__)
config = configure()

def _do_form(request):
    target = request.form.get('target')
    have_target = target not in ('', None)
    update = request.form.get('update')
    have_update = update not in ('', None)
    if have_update:
        update = 'ark:/%s' % (update.split('ark:/')[1],)
    ark_uri = None
    message = None
    alert_type = 'success' # see http://getbootstrap.com/components/#alerts
    try:
        if have_update and not have_target:
            #DELETE - We can't actually delete, but we can bind to ''.
            ark_uri = modify(config['ezid'], update)
            message = 'ARK now points nowhere.'
            alert_type = 'warning'
        elif have_target and not have_update:
            # MINT and BIND
            ark_uri = mint_and_bind(config['ezid'], target)
            message = 'Successfully minted new ARK.' 
        elif have_target and have_update:
            # MODIFY
            ark_uri = modify(config['ezid'], update, target)
            message = 'Successfully updated ARK.'
        else:
            # WTF?
            if request.method == 'POST':
                alert_type = 'warning'
                raise Exception('No data supplied')
    except Exception as e:
        alert_type = 'danger'
        message = e
    finally:
        return render_template('form.html', title=config['app_name'], ark=ark_uri, 
            message=message, target=target, alert_type=alert_type, 
            here=request.base_url)

@app.route('/', methods=['GET', 'POST'])
def index():
    if app.debug:
        return _do_form(request)
    else:
        # pass through CAS
        netid = None
        cas_url = config['cas']['url']
        if 'ticket' in request.form:
            netid = cas_validate(request, cas_url)
        if netid is None:
            params = { 'service' : request.base_url, 'method' : 'POST' }
            login_location = "%s/login?%s" % (cas_url, urlencode(params))
            return redirect(login_location, code=307)
        else:
            if netid in config['users']:
                return _do_form(request)
            else:
                return abort(403)

if __name__ == '__main__':
    app.run(debug=True)

