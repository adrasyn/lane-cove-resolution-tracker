"""Read-only runtime checks shared by local and future cloud daily runs."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def validate_runtime(config, location, platform, checkout):
    if location == 'local':
        binding = config['localBinding']
        if platform != binding['platform'] or checkout.resolve() != Path(binding['checkout']).expanduser().resolve():
            raise ValueError('Local execution requires the configured Mac checkout; do not impersonate local from cloud')


def validate_binding(config, location, remote, branch, dirty):
    if location not in ('local', 'cloud') or config['location'] != location:
        raise ValueError('Execution location differs from monitor/execution.json; do not run another scheduler')
    repository = config['repository']
    allowed = {f'https://github.com/{repository}', f'https://github.com/{repository}.git',
               f'git@github.com:{repository}.git', f'ssh://git@github.com/{repository}.git'}
    if remote not in allowed:
        raise ValueError('Origin does not match the configured repository')
    if branch != config['branch']:
        raise ValueError('Daily production runs must start on the configured main branch')
    if dirty:
        raise ValueError('Unfinished work exists; preserve it and stop before updating')


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.PIPE).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--location', required=True, choices=['local', 'cloud'])
    args = parser.parse_args()
    config = json.loads((ROOT / 'monitor/execution.json').read_text())
    validate_runtime(config, args.location, sys.platform, ROOT)
    for tool in ('git', 'curl', 'node', 'gh'):
        if not shutil.which(tool):
            raise ValueError(f'Missing required tool: {tool}')
    validate_binding(config, args.location, command('git', 'remote', 'get-url', 'origin'),
                     command('git', 'branch', '--show-current'), command('git', 'status', '--porcelain'))
    dependencies = {'pypdf': '6.21.2', 'pdfplumber': '0.11.8'}
    for package, version in dependencies.items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f'{package} must match the pinned dependency version {version}')
    identity = command('gh', 'api', 'user', '--jq', '.login')
    access = json.loads(command('gh', 'api', f'repos/{config["repository"]}', '--jq', '.permissions'))
    if not access.get('push'):
        raise ValueError('Existing GitHub identity lacks repository push permission')
    print(json.dumps({'status': 'passed', 'location': args.location, 'checkout': str(ROOT), 'platform': sys.platform, 'repository': config['repository'],
                      'branch': config['branch'], 'commit': command('git', 'rev-parse', 'HEAD'),
                      'githubIdentity': identity, 'githubPushPermission': True,
                      'dependencies': dependencies, 'node': command('node', '--version')}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError, importlib.metadata.PackageNotFoundError,
            subprocess.CalledProcessError) as error:
        raise SystemExit(f'Daily update preflight failed: {error}')
