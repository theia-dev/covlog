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
service apache2 reload
```

### Set up Apache
covlog.conf
```apacheconf
<VirtualHost *:80>
	ServerName covlog.example.com
    ServerAlias cl.example.com

    ServerAdmin admin@example.com

	Redirect permanent / https://covlog.example.com/
</VirtualHost>
```

covlog-ssl.conf
```apacheconf
<IfModule mod_ssl.c>
	<VirtualHost *:443>
		ServerName covlog.example.com
	    ServerAlias cv.example.com

	    ServerAdmin admin@example.com

	   	WSGIDaemonProcess covlog user=flask group=www-data threads=10 python-home=/var/www/covlog/covlog_venv

		WSGIProcessGroup covlog
	        WSGIApplicationGroup %{GLOBAL}

	    	WSGIScriptAlias / /var/www/quantup/covlog/covlog/covlog.wsgi

	       	ErrorLog ${APACHE_LOG_DIR}/covlog_ssl_error.log
	        CustomLog ${APACHE_LOG_DIR}/covlog_ssl_access.log combined

	    <Directory /var/www/covlog/covlog>
			Require all granted
	    </Directory>

	    SSLEngine on

		SSLProtocol             all -SSLv3 -TLSv1 -TLSv1.1
        SSLCipherSuite          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384
        SSLHonorCipherOrder     off
        SSLSessionTickets       off

	    SSLCertificateFile cert.pem
	   	SSLCertificateKeyFile key.pem
	    SSLCertificateChainFile chain.txt

		BrowserMatch "MSIE [2-6]" \
					nokeepalive ssl-unclean-shutdown \
					downgrade-1.0 force-response-1.0
		# MSIE 7 and newer should be able to use keepalive
		BrowserMatch "MSIE [17-9]" ssl-unclean-shutdown
	</VirtualHost>
</IfModule>
```