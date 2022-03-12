import re
import paramiko
import hashlib
import datetime
import sqlite3
import sys

from paramiko import *
from termcolor import colored
from datetime import datetime

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy)

DB_PATH = "/var/log/openvpn/ovpn.db"
# DB_PATH = "/home/mrandersen/openvpn.db"
OPENVPN_LOG = "/var/log/openvpn/status.log"
# OPENVPN_LOG = "/home/mrandersen/test.log"


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def connect_key(host, port, username):
    client.connect(hostname=host, port=port, username=username, key_filename='/home/mrandersen/.ssh/id_rsa.pub')

    stdin, stdout, stderr = client.exec_command('uname -a')
    text = stdout.read().decode('utf-8')

    print(colored('Connected ', 'green'), "{}:{}".format(host, port))
    print(text)

    return True


def execute_command(cmd):
    print(colored('>>>', 'green'), cmd)

    stdin, stdout, stderr = client.exec_command(cmd)

    code = stdout.channel.recv_exit_status()
    text = stdout.read().decode('utf-8')

    if code == 0:
        print(colored("OK", "green"))
    else:
        print(colored("ERROR", "red"), code)

    return text


def human_bytes(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def display_status(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = dict_factory

    today = datetime.today()
    date_string = today.strftime("%Y-%m-%d")

    result = connection.execute(
        "select username, sum(received) as received, sum(sent) as sent, max(datetime) as last_datetime "
        "from status where date = '{}' group by username".format(date_string)
    ).fetchall()

    for node in result:
        print(
            "{}\n\tTotal = {}\n\tUpload = {}\n\tDownload = {}\n\tLast Session = {}\n".format(
                node["username"],
                human_bytes(int(node["received"]) + int(node["sent"])),
                human_bytes(node["received"]),
                human_bytes(node["sent"]),
                node["last_datetime"]
            )
        )

    return True


def write_status_log_data(raw, db_path):
    array = []

    for entry in raw:
        chunked = entry.split(",")
        struct = {}

        struct["username"] = chunked[0]
        struct["ip"] = chunked[1].split(":")[0]
        struct["received"] = chunked[2]
        struct["sent"] = chunked[3]

        since_string = chunked[4]
        since_hash = hashlib.sha1(since_string.encode('utf-8')).hexdigest()

        struct["since_datetime"] = datetime.strptime(since_string, '%Y-%m-%d %H:%M:%S')
        struct["since_hash"] = since_hash

        array.append(struct)

    connection = sqlite3.connect(db_path)
    connection.row_factory = dict_factory

    connection.execute(
        "create table if not exists "
        "status (date text, datetime text, username text, received integer, sent integer, last_ip text, last_session_hash text)"
    )

    connection.execute(
        "create unique index if not exists status_index on status (date, username, last_session_hash)"
    )

    connection.commit()

    for node in array:
        date_string = node["since_datetime"].strftime("%Y-%m-%d")
        datetime_string = node["since_datetime"].strftime("%Y-%m-%d %H:%M:%S")

        connection.execute(
            "insert into status (date, datetime, username, received, sent, last_ip,  last_session_hash)"
            "values (?, ?, ?, ?, ?, ?, ?)"
            "on conflict (date, username, last_session_hash)"
            "do update set received = excluded.received, sent = excluded.sent",
            (
                date_string,
                datetime_string,
                node["username"],
                node["received"],
                node["sent"],
                node["ip"],
                node["since_hash"]
            )
        )

    connection.commit()
    connection.close()

    return array


def parse_log(log_contents):
    data = re.findall(r".*Updated,(.*)\n.*Since\n(.*)ROUTING", log_contents, re.MULTILINE | re.DOTALL)
    data = data[0][1]
    data = data.split("\n")
    data = list(filter(None, data))

    return data


def get_log_data_ssh():
    connect_key("time4vps", 44, "root")
    stdout = execute_command("cat /var/log/openvpn/status.log")
    return stdout


def get_log_data_local(path):
    f = open(path, "r")
    contents = f.read()
    f.close()

    return contents


if __name__ == '__main__':
    for arg in sys.argv:
        if arg == "--display":
            display_status(DB_PATH)
            exit(0)

    data = get_log_data_local(OPENVPN_LOG)
    data = parse_log(data)
    write_status_log_data(data, DB_PATH)

    exit(0)
