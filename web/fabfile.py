"""
This Fabfile contains the bootstrap and deploy methods plus related
subroutines required to deploy with the Mail Checkup service.

`bootstrap` and `deploy` are executed as the command line ``fab`` program
and takes care of setting up a new system, installing required libraries
or programs, setting up the server, and deploying the newest version of the
website from github.

`fab environment action`

Available Environments:     Available Actions:
dev                         bootstrap:  Sets up system by installing programs,
production                              runs deploy afterwards
staging                     deploy:     uploads conf/ files and gets newest code
                                        from github
                            get_database:will get the database rip from that
                                        server and store it in conf/
                            put_templates:will upload the newest templates from
                                          the conf/ directory

Useful commands:
`fab dev bootstrap` : after running vagrant up, this will install MailCheckup
                      locally
`fab dev deploy` : this should be used to update to the newest version of the
                   website locally
`fab production deploy` : deploys the newest version of the website LIVE

The other callables defined in this module are internal only.
"""

from __future__ import with_statement
from fabric.contrib.files import exists, append, upload_template
from fabric.contrib.project import rsync_project
from fabric.colors import white, blue, red
from fabric.api import env, run as _run, sudo, local, put, cd, settings, hide, prompt, get
from fabric.utils import puts
from pprint import pprint

import time
import os

#environment variables shared
#env.ssh_config_path = 'conf/ssh_config'
#env.use_ssh_config = True
env.forward_agent = True
env.debug = False
env.project_name = 'mailcheckup'
env.project_title = 'Mail Checkup'
env.repository = 'git@bitbucket.org:htmlgraphic/%s.git' % env.project_name
env.branch = "develop"
env.db_root_password = None
env.templates = {}
env.colors = True

def config_templates():
    env.templates = {
    "apache": {
        "local_path": "conf/vhosts.conf",
        "remote_directory": "/etc/apache2/sites-available/",
        "remote_path": "/etc/apache2/sites-available/%s.conf" % env.project_name,
    },
    "php": {
        "local_path": "conf/php.ini",
        "remote_directory": "/etc/php5/apache2/",
        "remote_path": "/etc/php5/apache2/php.ini",
    },
    "cron": {
        "local_path": "conf/crontab",
        "remote_directory": "/etc/cron.d/",
        "remote_path": "/etc/cron.d/%s" % env.project_name,
        "owner": "root",
        "mode": "600",
    },
    "non-CI": {
        "local_path": "conf/connection.inc.php",
        "remote_directory": "%s/public_html/includes/" % env.project_directory,
        "remote_path": "%s/public_html/includes/config.inc.php" % env.project_directory,
    },
    "CI": {
        "local_path": "conf/database.php",
        "remote_directory": "%s/application/config/" % env.project_directory,
        "remote_path": "%s/application/config/database.php" % env.project_directory,
    },
    "sslcert": {
        "local_path": "conf/www.mailcheckup.com/ssl.crt",
        "remote_directory": "/etc/apache2/ssl.crt/",
        "remote_path": "/etc/apache2/ssl.crt/www.mailcheckup.com.crt",
    },
    "sslkey": {
        "local_path": "conf/www.mailcheckup.com/ssl.key",
        "remote_directory": "/etc/apache2/ssl.key/",
        "remote_path": "/etc/apache2/ssl.key/www.mailcheckup.com.crt",
    },
    # "samba": {
    #     "local_path": "conf/smb.conf",
    #     "remote_directory": "/etc/samba/",
    #     "remote_path": "/etc/samba/smb.conf",
    # },
}

def dev():
    vagrant_config = get_vagrant_parameters('dev')
    env.name = 'development'
    env.user = vagrant_config['User']
    env.db_name = 'mc_development'
    env.db_user = env.user
    env.db_password = 'devpassword'
    env.domain = 'localhost'
    env.hosts = ['%s:%s' % (vagrant_config['HostName'],
                    vagrant_config['Port'])]
    env.key_filename = vagrant_config['IdentityFile']
    env.debug = True
    env.project_directory = '/home/%s/%s' % (env.user, env.project_name)
    env.project_root = '/home/%s' % env.user
    env.is_live = 0
    config_templates()


def production():
    vagrant_config = get_vagrant_parameters('web')
    env.name = 'production'
    env.user = vagrant_config['User']
    env.db_name = 'mc_production'
    env.db_user = 'production'
    env.db_password = 'prodpassword'
    env.domain = 'mailcheckup.com'
    env.hosts = ['%s:%s' % (vagrant_config['HostName'],
                    vagrant_config['Port'])]
    env.key_filename = vagrant_config['IdentityFile']
    env.project_directory = '/home/%s/%s' % (env.user, env.project_name)
    env.project_root = '/home/%s' % env.user
    env.is_live = 1
    config_templates()


def staging():
    vagrant_config = get_vagrant_parameters('web')
    env.name = 'staging'
    env.user = vagrant_config['User']
    env.db_name = 'mc_staging'
    env.db_user = 'staging'
    env.db_password = 'stagingpassword'
    env.domain = 'staging.mailcheckup.com'
    env.hosts = ['staging.mailcheckup.com']
    env.key_filename = vagrant_config['IdentityFile']
    env.project_directory = '/home/%s/%s' % (env.user, env.project_name)
    env.project_root = '/home/%s' % env.user
    env.is_live = 0
    config_templates()


def get_ssh_param(params, key):
    import re
    return filter(lambda s: re.search(r'^%s' % key, s), params)[0].split()[1]


def apt(packages):
    return sudo("apt-get install -y -q " + packages)


def run(command, show=True):
    with hide("running"):
        return _run(command)


def bootstrap():
    """
    Runs once
    """

    append("~/.bash_profile", "alias vi=vim")
    append("~/.bash_profile", "alias l=ls")
    append("~/.bash_profile", "alias ll='ls -al'")
    append("~/.bash_profile", "export PROJECT_NAME=%s" % env.project_name)
    append("~/.bash_profile", "export VAGRANT_ROOT=/vagrant/deploy")

    sudo("apt-get update")

    #install vim to help edit files faster
    apt("vim")

    #install apc prerequisites
    apt("make libpcre3 libpcre3-dev re2c")

    #install python 2.6 (needed for google sitemaps, remove for now)
    #apt("python2.6")

    #only install samba if we are bootstrapping locally
    # if env.name == "development":
    #     apt("samba")
    #     #we only need to run this once, so it goes in bootstrap not deploy
    #     sudo("smbpasswd -a %s" % env.user) # You can't set a SAMBA user if they don't exist on the system /etc/passwd. Also, this does not work without a password given at command line.

    #install_dependencies and lamp
    apt("tasksel rsync")
    apt("apache2 php5 libapache2-mod-php5 php5-mcrypt mysql-server libapache2-mod-auth-mysql \
            php5-mysql")

    apt("php-apc")

    #install curl, used for Composer
    apt("curl")

    sudo("a2enmod php5")
    sudo("a2enmod rewrite")
    sudo("a2enmod headers")
    sudo("a2enmod expires")

    #ensure apache is started at this point
    start_server()

    apt("php-pear php5-dev php5-curl")

    #run this AFTER we install apache, or the following error will happen
    #apache2: Could not reliably determine the server's fully qualified domain name, using 127.0.1.1 for ServerName
    sudo('''sh -c "echo 'ServerName MailCheckup.com' > /etc/apache2/conf-available/servername.conf"''')
    #sudo('sh -c \047echo \042ServerName mailcheckup.com\042 > /etc/apache2/httpd.conf\047') # alternate method

    #install git
    apt("git-core")



    print(white("If you have an authentication error occurs connecting to git, run $ ssh-add"))

    #check key to see if it exists, only generate new key if one isnt already made.
    if not exists("%s/.ssh/id_rsa" % env.project_root):
        print(white("Trying to run automatically, please enter your desired password when prompted."))
        local("ssh-add")

    deploy()



def deploy():
    #UPDATE the server with the newest updates from github.

    print(white("Creating environment %s" % env.name))

    #if the directory doesnt exist, clone the repository
    if not exists("%s" % env.project_directory):
        #TODO: do a more proper clone, so it doesnt say x commits ahead of origin/2.0
        with cd("%s" % env.project_root):
            #TODO: set up known_hosts before cloning to bypass key/security prompt
            run("git clone %s" % env.repository)
        #ensure we are in the right branch!
        with cd("%s" % env.project_directory):
            run("git checkout %s" % env.branch)

    #if the directory does exist, just fetch updates
    else:
        #ensure we are in the right branch!
        with cd("%s" % env.project_directory):
            run("git checkout %s" % env.branch)
            #make sure we dont have any non-overwritable local changes
            #TODO, remove envconfig.php from repo, and remove the reset and clean commands.
            run("git reset --hard HEAD")
            #clean any untracked files so we have no conflicts
            run("git clean -f")
            #then pull
            run("git pull %s %s" % (env.repository, env.branch))


    #make sure logs directory exists
    if not exists("%s/application/logs/" % env.project_directory):
        with cd("%s/application" % env.project_directory):
            sudo("mkdir logs")

    #ensure everything is writable in the logs dir
    with cd("%s/application/" % env.project_directory):
        sudo("chown www-data:www-data -R logs")
        sudo("chmod 777 -R logs")

    #install curl, used with composer
    apt("curl")

    sudo("curl -sS https://getcomposer.org/installer | php")
    sudo("mv composer.phar /usr/local/bin/composer")

    #download any php libraries needed for this system
    with cd("%s/" % env.project_directory):
        sudo("composer update")

    put_templates()

    #We need to restart samba if this is a dev server
    # if env.name == "development":
    #     sudo("service smbd restart")

    if not exists("%s/log" % env.project_directory):
        with cd("%s" % env.project_directory):
            sudo("mkdir log")

    if not exists("%s/log/error_log" % env.project_directory):
        with cd("%s/log" % env.project_directory):
            sudo("touch error_log")

    #make sure we have ssl enabled
    sudo('a2enmod ssl')

    #make sure correct apache symlinks are created
    #and proper deploy config is loaded
    sudo('a2ensite %s.conf' % env.project_name)

    #disable the default website
    sudo('a2dissite 000-default')

    #set the 'ServerName' directive globally
    sudo('a2enconf servername')

    #ensure the crontab is enabled
    sudo('crontab -u %s /etc/cron.d/%s' % (env.user, env.project_name))

    restart_server()

    init_db()


def start_server():
    #starts apache and mysql
    try:
        sudo("apache2ctl -k start", pty=False)
    except:
        pass


def stop_server():
    #stops apache and mysql
    try:
        sudo("apache2ctl -k stop", pty=False)
    except:
        pass


def restart_server():
    #this command will restart apache if it is running, and start it if it is not running
    sudo("apache2ctl -k restart", pty=False) #running this command after the system is up causes an issue, since the "service apache2 start" command does not work in this script, can we check if apache is running and skip


def init_db():
    mysql_create_user(env.db_user, env.db_password)

    with settings(warn_only=True):
        run('mysqladmin -u %s -p%s create %s' % (env.db_user, env.db_password, env.db_name)) # can fail

    put("conf/mysql-restore.sql", "/tmp/mysql-restore.sql")

    with settings(warn_only=True):
        run('mysql -u %s -p%s %s < /tmp/mysql-restore.sql' % (env.db_user, env.db_password, env.db_name))


def get_vagrant_parameters(box):
    """
    Parse vagrant's ssh-config for given key's value
    This is helpful when dealing with multiple vagrant instances.
    """
    result = local('vagrant ssh-config ' + box, capture=True)
    conf = {}
    for line in iter(result.splitlines()):
        parts = line.split()
        conf[parts[0]] = ' '.join(parts[1:])

    return conf


def backup_database():
    date = time.strftime('%F-%H%M%S')

    filename = '/backups/%(environment)s/%(date)s-%(database)s-backup.sql.gz'\
        % {
        'environment': env.user,
        'database': env.db_name,
        'date': date,
        }

    if exists(filename):
        run('rm "%s"' % filename)

    run('mysqldump -u %(username)s -p %(password)s %(database)s | '
        'gzip > %(filename)s' % {'username': env.db_user,
        'password': env.db_password,
        'database': env.db_name,
        'filename': filename})


def restore_latest_backup():
    # TODO: use 'with cd(' if possible
    run('cd backups/%(environment)s | gunzip < $(ls -1 | tail -n 1) | \
            mysql -u %(username)s -p %(password)s %(database)s' %
        {'environment': env.user,
        'username': env.db_user,
        'password': env.db_password,
        'database': env.db_name})
    run('cd ../..')

def put_templates():
    for name in get_templates():
        upload_environment_templates(name)


def get_templates():
    """
    Injects environment variables into config templates
    """
    injected = {}
    for name, data in env.templates.items():
        injected[name] = dict([(k, v % env) for k, v in data.items()])
    return injected


def upload_environment_templates(name):
    print(blue("Uploading template: %s" % name))

    template = get_templates()[name]
    local_path = template["local_path"]
    remote_directory = template["remote_directory"]
    remote_path = template["remote_path"]
    owner = template.get("owner")
    mode = template.get("mode")

    if not exists("%s" % remote_directory):
        sudo("mkdir -p %s" % remote_directory)

    upload_template(local_path, remote_path, env, use_sudo=True, backup=False)
    if owner:
        sudo("chown %s %s" % (owner, remote_path))
    if mode:
        sudo("chmod %s %s" % (mode, remote_path))

    print(blue("Uploaded template: %s" % name))

def add_user(user=None):
    if not exists("%s" % env.project_root):
        sudo('useradd %s -s /bin/bash -m' % env.user)
        sudo('echo "%s ALL=(ALL) ALL" >> /etc/sudoers' % env.user)
        password = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(8))
        sudo('echo "%s:%s" | chpasswd' % (env.user, password))
        print(red("Password for %s is %s" % (env.user, password)))


def mysql_create_user(db_user=None, db_password=None):
    """ Creates mysql user. """
    if _mysql_user_exists(db_user):
        puts('User %s already exists' % db_user)
        return

    sql = "GRANT ALL ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s';" % (env.db_name, db_user, db_password)

    mysql_execute(sql, 'root')

def _mysql_user_exists(db_user):
    sql = "SHOW GRANTS FOR '%s'@localhost" % db_user
    with settings(hide('warnings', 'running', 'stdout', 'stderr'), warn_only=True):
        result = mysql_execute(sql, 'root')
    return result.succeeded

def mysql_execute(sql, user=None, password=None):
    """ Executes passed sql command using mysql shell. """
    user = user or env.db_user

    if user == 'root' and password is None:
        password = _get_root_password()
    elif password is None:
        password = env.db_password

    sql = sql.replace('"', r'\"')
    return run('echo "%s" | mysql --user="%s" --password="%s"' % (sql, user , password))

def _get_root_password():
    """Ask root password only once if needed"""
    if env.db_root_password is None:
        env.db_root_password = prompt('Please enter MySQL root password:')
    return env.db_root_password

def get_database():
    with cd("~"):
        run("mysqldump -u %s -p%s %s >> mysql-restore.sql"
        % (env.db_user, env.db_password, env.db_name))
        get("~/mysql-restore.sql", "conf/mysql-restore.sql")
        run("rm ~/mysql-restore.sql")

def create_sitemap():
    run('python /etc/rc.d/google_sitemaps/sitemap_gen.py --config=%s/config.xml' % env.project_directory)
