#!/usr/bin/env python

from cStringIO import StringIO
from configobj import ConfigObj
from datetime import timedelta
from flask import Flask
from flask import Markup
from flask import abort
from flask import g
from flask import make_response
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from os import path
from requests import get
from requests import post
from requests.auth import HTTPBasicAuth
from sys import exit
from sys import stderr
from urllib import urlencode
import sqlite3 as sqlite

SESSION_KEY = 'arkform'

####################
## Initialization ##
####################

def project_dir():
    return path.dirname(path.dirname(path.realpath(__file__)))

def normalize_base_url(url):
    if url[-1:] != '/':
        url = url + '/'
    return url

def configure():
    '''Note that this uses [configobj][1] rather than the standard 
    library.

     1: https://github.com/DiffSK/configobj
    '''
    config_fp = '/etc/arkform.conf'
    if __name__ == '__main__':
        config_fp = path.join(project_dir(), 'etc/arkform.conf')

    config = ConfigObj(config_fp, unrepr=True)

    # Normalize trailing slashes (to include)
    config['cas']['url'] = normalize_base_url(config['cas']['url'])
    config['ezid']['service'] = normalize_base_url(config['ezid']['service'])
    config['ezid']['resolver'] = normalize_base_url(config['ezid']['resolver'])
    return config

def init_db(file_path):
    '''Easier than including a schema with the app.
    '''
    if not path.exists(file_path):
        con = sqlite.connect(file_path)
        try:
            cur = con.cursor()
            cur.execute('''CREATE TABLE IF NOT EXISTS 
                arks(
                  target TEXT NOT NULL,
                  ark TEXT NOT NULL
                );''')
            cur.execute('CREATE INDEX target_idx ON arks(target);')
            cur.execute('CREATE INDEX ark_idx ON arks(ark);')
            con.commit()
        except sqlite.Error, e:
            if con:
                con.rollback()
            stderr.write(str(e)+'\n')
            exit(1)
        finally:
            if con: 
                con.close()

try:
    app = Flask(__name__)
    config = configure()
    init_db(config['db']['path'])
    app.secret_key = config['cas']['secret']
    session_lifetime = timedelta(seconds=config['cas']['session_age'])
    app.permanent_session_lifetime = session_lifetime
except Exception as e:
    stderr.write(str(e)+'\n')
    exit(1)


########################
## Database functions ##
########################

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite.connect(config['db']['path'])
    return db

@app.teardown_appcontext
def close_connection(exception):
    '''[Callback that closes the database connection for us][1].

     1: http://flask.pocoo.org/docs/patterns/sqlite3/#using-sqlite-3-with-flask
    '''
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def db_put(ark, target):
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM arks WHERE ark=?", (ark,))
    row = cur.fetchone()
    q = ''
    if row is None:
        q = "INSERT INTO arks (target, ark) VALUES (?,?)"
    else:
        q = "UPDATE arks SET target=? WHERE ark=?"
    cur.execute(q, (target, ark))
    con.commit()

def db_get(target):
    cur = get_db().cursor()
    q = "SELECT * FROM arks WHERE target=?"
    cur.execute(q, (target,))
    row = cur.fetchone()
    return row if row else None

#############################
## Web Application Helpers ##
#############################

def cas_validate(request, cas_url):
    params = { 'service' : request.base_url,'ticket' : request.form['ticket'] }
    validate_url = "%svalidate" % (cas_url,)
    resp = get(validate_url, params=params)
    body = StringIO(resp.content).readlines()
    if body[0].strip() == 'yes':
        return body[1].strip()
    else:
        return None

def modify(config, ark, base_url, target_url=None):
    '''Modify an existing ARK. If the target_url parameter is not included,
    the ARK is marked as [withdrawn][1], and the target is set to this 
    application's `/withdrawn` page.

     1: http://ezid.cdlib.org/doc/apidoc.html#internal-metadata
    '''

    row = db_get(target_url)
    if row is not None and row[0] != '%swithdrawn' % (base_url,):
        raise Exception('%s is already bound to %s' % (to_href(row[0]),to_href(row[1])))
    
    body = 'who:%s' % (config["who"],)

    if target_url in ('', None):
        body += '\n_status:unavailable | withdrawn'
        target_url = '%s%s' % (normalize_base_url(request.base_url), 'withdrawn')
    body += '\n_target:%s' % (target_url,)

    url = '%sid/%s' % (config['service'], ark)
    auth = HTTPBasicAuth(config['user'], config['password'])
    headers = { 'content-type' : 'text/plain' }
    resp = post(url, auth=auth, data=body, headers=headers)

    if resp.status_code == 200:
        ark = '%s%s' % (config['resolver'], ark)
        db_put(ark, target_url)
        return ark
    else:
        raise Exception(resp.content)

def mint_and_bind(config, target_url):
    '''Mint and bind in one request, as shown in the [EZID cURL examples][1].

     1: http://ezid.cdlib.org/doc/apidoc.html#curl-examples
    '''
    row = db_get(target_url)
    if row is not None:
        raise Exception('%s is already bound to %s' % (to_href(row[1]),to_href(row[0])))

    body = '_target:%s\nerc:who:%s' % (target_url,config["who"])
    url = '%sshoulder/%s' % (config['service'], config['shoulder'])
    auth = HTTPBasicAuth(config['user'], config['password'])
    headers = { 'content-type' : 'text/plain' }
    resp = post(url, auth=auth, data=body, headers=headers)

    if resp.status_code == 201:
        # swap in Princeton's resolver
        ark = '%s%s' % (config['resolver'], resp.content.split(': ')[1].strip())
        db_put(ark, target_url)
        return ark
    else:
        raise Exception(resp.content)

## The Form ##
def to_href(uri):
    return '<a class="alert-link" href="%s">%s</a>' % (uri,uri)

def update_message(target, ark):
    message = '<br/>%s' % (to_href(ark),)
    message += ' <span class="glyphicon glyphicon-arrow-right"></span> '
    message += to_href(target)
    return message

def form(request, netid):
    target = request.form.get('target')
    have_target = target not in ('', None)
    update = request.form.get('update')
    have_update = update not in ('', None)
    lookup = request.form.get('lookup')
    have_lookup = lookup not in ('', None)
    if have_update:
        update = 'ark:/%s' % (update.split('ark:/')[1],)
    ark_uri = None
    message = None
    alert_type = 'success' # see http://getbootstrap.com/components/#alerts
    base = normalize_base_url(request.base_url)
    try:
        if have_lookup:
            # LOOKUP
            row = db_get(lookup)
            if row:
                message = '%s is bound to %s' % (to_href(lookup), to_href(row[1]))
            else:
                message = '%s is not bound to an ARK in this system.' % (to_href(lookup),)
        elif have_update and not have_target:
            # WITHDRAW
            ark_uri = modify(config['ezid'], update, base)
            withdrawn_uri = '%swithdrawn' % (base)
            message = 'ARK now points to %s.' % (to_href(withdrawn_uri),)
            alert_type = 'warning'
        elif have_target and not have_update:
            # MINT and BIND
            ark_uri = mint_and_bind(config['ezid'], target)
            message = 'Successfully minted new ARK.' 
            message += update_message(target, ark_uri)
        elif have_target and have_update:
            # MODIFY
            ark_uri = modify(config['ezid'], update, base, target)
            message = 'Successfully updated ARK.'
            message += update_message(target, ark_uri)
        else:
            # WTF?
            if request.method == 'POST' and not 'ticket' in request.form:
                alert_type = 'warning'
                raise Exception('No data supplied')
    except Exception as e:
        alert_type = 'danger'
        message = e
    finally:
        return render_template('form.html', title=config['app_name'], 
            message=Markup(message), alert_type=alert_type, 
            here=request.base_url, netid=netid)

##############
### Routes ###
##############

@app.route('/', methods=['GET', 'POST'])
def index():
    netid = None
    if SESSION_KEY in session:
        netid = session[SESSION_KEY]
        return form(request, netid)
    else:
        cas_url = config['cas']['url']
        if 'ticket' in request.form:
            netid = cas_validate(request, cas_url)
        if netid is None:
            params = { 'service' : request.base_url, 'method' : 'POST' }
            login_location = "%slogin?%s" % (cas_url, urlencode(params))
            return redirect(login_location, code=307)
        else:
            if netid in config['users']:
                session.permanent = True
                session[SESSION_KEY] = netid
                return form(request, netid)
            else:
                base = normalize_base_url(request.base_url)
                location = '%snot_authorized' % (base,)
                return redirect(location, code=302)

@app.route('/withdrawn', methods=['GET'])
def tombstone():
    title = '%s: %s' % (config['app_name'], 'Not Found')
    resp = make_response(render_template('tombstone.html', title=title))
    resp.status_code = 404
    return resp

@app.route('/notauth', methods=['GET'])
def not_authorized():
    title = '%s: %s' % (config['app_name'], 'Not Authorized')
    resp = make_response(render_template('not_authorized.html', title=title))
    resp.status_code = 403
    return resp

@app.route('/logout', methods=['GET'])
def logout():
    if SESSION_KEY in session:
        del session[SESSION_KEY]
        cas_url = config['cas']['url']
        params = { 'service' : request.base_url }
        location = "%slogout?%s" % (cas_url, urlencode(params))
        return redirect(location, code=307)
    else:
        title = '%s: %s' % (config['app_name'], 'Logged Out')
        return render_template('logged_out.html', title=title)


if __name__ == '__main__':
    app.run(debug=True)

