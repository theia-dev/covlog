# COVLOG
## About
COVLOG is a simple web tool to trace people across multiple locations with privacy in mind.

## Setup
### Preparation
* Using Apache [mod_wsgi](https://flask.palletsprojects.com/en/1.1.x/deploying/mod_wsgi/)
* install wsgi `apt-get install libapache2-mod-wsgi-py3`
* enable the mod `sudo a2enmod wsgi`
* install python3 `apt-get install python3.4` (or higher)
* install virtual environment `apt-get install sudo apt-get install python-virtualenv`
* install git `apt-get install git`
* create flask user `sudo useradd -r -s /bin/false flask`
* create flask users home `sudo mkdir /home/flask`
* set rights on folder `sudo chown flask:www-data /home/flask`


### Install the source
* Prepare folder
    * `cd /var/www/`
    * `mkdir covlog`
    * `cd covlog`
* Get files
    * `git clone https://github.com/theia-dev/covlog.git`
    * `virtualenv --python=python3 covlog_venv`
    * `. ./covlog_venv/bin/activate`
    * `pip install --upgrade pip`
    * `pip install -r ./covlog/requirements.txt`
* Create db and set first admin user
    * `python initial_setup.py`
* Add git hook  under `.git/hooks/post-merge ` to make updates easier
```bash
#!/bin/bash
git log -1 > /var/www/covlog/covlog/version.txt
chown -R flask:www-data /var/www/covlog/covlog/
touch /var/www/covlog/covlog/covlog.wsgi
```
* make executable ```chmod +x .git/hooks/post-merge```

### Set up Apache
* Create config files ```covlog.conf``` 
* Activate sites ```a2ensite covlog covlog-ssl```
* Run ```letsencrypt``` and select the new page - choose "2: Redirect - Make all requests redirect to secure HTTPS access."



covlog.conf
```apacheconf
<IfModule mod_ssl.c>
    <VirtualHost *:443>
        ServerName covlog.example.com
        ServerAlias cv.example.com

        ServerAdmin admin@example.com

        WSGIDaemonProcess covlog user=flask group=www-data threads=10 python-home=/var/www/covlog/covlog_venv
        WSGIProcessGroup covlog
        WSGIApplicationGroup %{GLOBAL}

        WSGIScriptAlias / /var/www/covlog/covlog/covlog.wsgi

        ErrorLog ${APACHE_LOG_DIR}/covlog_error.log
        CustomLog ${APACHE_LOG_DIR}/covlog_access.log combined

        <Directory /var/www/covlog/covlog>
            Require all granted
        </Directory>

    </VirtualHost>
</IfModule>
```