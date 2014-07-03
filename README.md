PUL ARKs Form
=============

Simple web form for minting and binding ARKs @ PUL.

To install run `./setup.py install` (with sudo if necessary), and set config options in `/etc/arkform.conf`.

You'll need Apache, Python 2.7 and mod-wsgi (e.g. `sudo apt-get install libapache2-mod-wsgi`).

The configuration for Apache should look something like this:

```
WSGIDaemonProcess arkform user=USER group=GROUP processes=2 threads=5 maximum-requests=10000
WSGIScriptAlias /arkform /var/www/arkform.wsgi
WSGIProcessGroup arkform
```

It probably makes sense to make a user/group just for the app.


