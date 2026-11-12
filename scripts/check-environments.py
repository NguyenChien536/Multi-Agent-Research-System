"""Verify two running local environments using disposable accounts, without providers."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parents[1]


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.DEVNULL).strip()


def container(project, service):
    ids = docker('ps', '-q', '--filter', f'label=com.docker.compose.project={project}',
                 '--filter', f'label=com.docker.compose.service={service}').splitlines()
    assert len(ids) == 1, f'Expected one running {service} in {project}'
    return json.loads(docker('inspect', ids[0]))[0]


def request(base, path, method='GET', body=None, token=None, expected=200):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(base + path, method=method, headers=headers,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            code, data = response.status, response.read()
    except urllib.error.HTTPError as exc:
        code, data = exc.code, exc.read()
    assert code == expected, f'{method} {path}: HTTP {code}, expected {expected}'
    return json.loads(data) if data else None


def check(args):
    for url in (args.prod_url, args.dev_url):
        parsed = urllib.parse.urlsplit(url)
        assert parsed.hostname in {'127.0.0.1', 'localhost'} and parsed.scheme == 'http', 'Use local HTTP URLs only'
        assert not parsed.username and not parsed.password and parsed.path in {'', '/'}, 'Use an origin URL without credentials'
    assert args.prod_project != args.dev_project and args.prod_url != args.dev_url
    backends = [container(args.prod_project, 'backend'), container(args.dev_project, 'dev-backend')]
    pg = [container(args.prod_project, 'postgres'), container(args.dev_project, 'dev-postgres')]
    redis = [container(args.prod_project, 'redis'), container(args.dev_project, 'dev-redis')]
    environments = [dict(item.split('=', 1) for item in c['Config']['Env']) for c in backends]
    assert [env['ENVIRONMENT'] for env in environments] == ['production', 'development']
    assert environments[0]['APP_SECRET_KEY'] != environments[1]['APP_SECRET_KEY'], 'Signing/encryption secrets must differ'
    assert environments[0]['DATABASE_URL'] != environments[1]['DATABASE_URL']
    groups = [[*backends[:1], *pg[:1], *redis[:1]], [*backends[1:], *pg[1:], *redis[1:]]]
    volumes = [{m['Name'] for c in group for m in c['Mounts'] if m['Type'] == 'volume'} for group in groups]
    networks = [{n['NetworkID'] for c in group for n in c['NetworkSettings']['Networks'].values()} for group in groups]
    assert volumes[0].isdisjoint(volumes[1]) and networks[0].isdisjoint(networks[1]), 'Private volumes/networks must be separate'
    assert not any(m['Type'] == 'bind' and m['Destination'] == '/app/app' for m in backends[0]['Mounts'])
    assert any(m['Type'] == 'bind' and m['Destination'] == '/app/app' for m in backends[1]['Mounts'])
    print('PASS: modes, private secrets, database/file volumes, networks and source mounts are separated', flush=True)

    accounts = []
    redis_key = 'synthia:environment-check:' + uuid.uuid4().hex
    urls = [args.prod_url.rstrip('/'), args.dev_url.rstrip('/')]
    identity = uuid.uuid4().hex[:16]
    try:
        for index, base in enumerate(urls):
            assert request(base, '/api/v1/ready')['status'] == 'ready'
            password = 'EnvironmentCheck!' + uuid.uuid4().hex
            value = {'username': 'env_check_' + identity, 'email': identity + '@example.com', 'password': password}
            user = request(base, '/api/v1/auth/register', 'POST', value, expected=201)
            token = request(base, '/api/v1/auth/login', 'POST', {'email': value['email'], 'password': password})['access_token']
            accounts.append({'base': base, 'token': token, 'password': password, 'id': str(uuid.UUID(user['id']))})
            task = request(base, '/api/v1/research', 'POST', {
                'title': 'Environment separation check',
                'research_question': 'Are these disposable research records isolated between environments?',
            }, token=token, expected=201)
            accounts[-1]['task_id'] = task['id']
        assert accounts[0]['id'] != accounts[1]['id']
        for index, account in enumerate(accounts):
            other = accounts[1-index]
            request(account['base'], '/api/v1/auth/me', token=other['token'], expected=401)
            request(account['base'], '/api/v1/research/' + other['task_id'], token=account['token'], expected=404)
            request(account['base'], '/api/v1/auth/me', token=account['token'])
        print('PASS: identical usernames/emails coexist independently; tokens and research do not cross environments', flush=True)
        for index, c in enumerate(redis):
            assert docker('exec', c['Id'], 'redis-cli', 'SET', redis_key, str(index)) == 'OK'
        for index, c in enumerate(redis):
            assert docker('exec', c['Id'], 'redis-cli', 'GET', redis_key) == str(index)
        print('PASS: Redis values and queues use separate instances', flush=True)
    finally:
        for c in redis:
            docker('exec', c['Id'], 'redis-cli', 'DEL', redis_key)
        for account in accounts:
            request(account['base'], '/api/v1/auth/me', 'DELETE', {
                'current_password': account['password'], 'confirmation': 'DELETE',
            }, token=account['token'], expected=202)
        deadline = time.monotonic() + 60
        for index, account in enumerate(accounts):
            query = "SELECT count(*) FROM users WHERE id='" + account['id'] + "';"
            while docker('exec', pg[index]['Id'], 'psql', '-U', 'research_user', '-d', 'research_db', '-Atc', query) != '0':
                assert time.monotonic() < deadline, 'Disposable account cleanup still pending; durable intent retained'
                time.sleep(1)
    print('PASS: disposable accounts/tasks cleaned through each environment; no model/search calls', flush=True)


if __name__ == '__main__':
    active_file = ROOT / 'scratch/local-active.json'
    active = json.loads(active_file.read_text(encoding='utf-8-sig')) if active_file.exists() else {}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prod-project', default=active.get('project', 'synthia-release'))
    parser.add_argument('--prod-url', default='http://127.0.0.1:' + str(active.get('port', 3080)))
    parser.add_argument('--dev-project', default='synthia-dev')
    parser.add_argument('--dev-url', default='http://127.0.0.1:3000')
    check(parser.parse_args())
