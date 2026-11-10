#!/usr/bin/env python3
"""Read-only API/Qwen checks; never print service credentials or user records."""
import json
import os
import sys
import urllib.request
import urllib.error


def probe(url, token=''):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=12) as response:
        return json.load(response)


def main():
    api = os.getenv('UNICRON_API_URL', 'http://127.0.0.1:42515').rstrip('/')
    token = os.getenv('UNICRON_API_TOKEN') or os.getenv('CIVITAS_API_KEY', '')
    model = os.getenv('CIVITAS_LLM_BASE_URL', 'http://127.0.0.1:42516/v1').rstrip('/')
    model_token = os.getenv('CIVITAS_LLM_API_KEY', '')
    failed = False
    for name, url, secret in [('API health', api + '/api/health', token),
                              ('Authenticated API', api + '/api/cases', token),
                              ('Qwen models', model + '/models', model_token)]:
        try:
            result = probe(url, secret)
            if name == 'Qwen models':
                ids = [entry.get('id') for entry in result.get('data', [])]
                configured = os.getenv('CIVITAS_LLM_MODEL')
                if configured and configured not in ids:
                    print(name + ': configured model is not advertised by this server')
                    failed = True
                    continue
            print(name + ': reachable')
        except urllib.error.HTTPError as exc:
            print(name + ': HTTP ' + str(exc.code))
            failed = True
        except (OSError, ValueError, TypeError):
            print(name + ': unavailable or returned invalid JSON')
            failed = True
    if not api.startswith('https://'):
        print('Hosted connection: needs an HTTPS API address; localhost works only on this laptop.')
    print('This check does not run inference or a six-agent investigation.')
    return int(failed)

if __name__ == '__main__':
    sys.exit(main())
