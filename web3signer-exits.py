#! /usr/bin/env nix-shell
#! nix-shell -i python --packages python3 python3Packages.requests

# Based on https://github.com/lidofinance/validator-exits-automation-snippets/blob/main/web3signer.mjs

# Example usage:
# web3signer-exits.py --cl=http://127.0.0.1:5052 --web3signer=http://127.0.0.1:9000 auto
# or
# web3signer-exits.py --cl=http://127.0.0.1:5052 --web3signer=http://127.0.0.1:9000 auto

import requests
import json
import argparse
import subprocess


def SignExitMessage(pubKey, cl, web3signer, fork, genesis_validators_root,
                    current_epoch, verify):
  validator_response = requests.get(
    f"{cl}/eth/v1/beacon/states/head/validators/{pubKey}")
  if validator_response.status_code != 200:
    print(f"Could not get validator index for {pubKey}. Error: {validator_response.reason}")
    return
  validator_index = validator_response.json()['data']['index']

  # Construct voluntary exit message
  voluntary_exit = {
      'epoch': str(current_epoch),
      'validator_index': validator_index,
  }

  body = {
      'type': 'VOLUNTARY_EXIT',
      'fork_info': {
          'fork': fork,
          'genesis_validators_root': genesis_validators_root,
      },
      'voluntary_exit': voluntary_exit,
  }

  signer_response = requests.post(
      f"{web3signer}/api/v1/eth2/sign/{pubKey}",
      data=json.dumps(body),  # Convert body to JSON string
      headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
  )
  signature = signer_response.json()
  signed_message = {
      'message': voluntary_exit,
      'signature': signature['signature'],
  }

  fn = f"{validator_index}-{pubKey}.json"
  with open(fn, "w") as f:
    f.write(json.dumps(signed_message))

  if verify:
    res = subprocess.run(["ethdo","exit","verify",f"--connection={cl}",f"--signed-operation={fn}"])
    if res.returncode != 0:
      print(f"Error: ethdo verification of {fn} for validator {pubkey} failed.")
      return
    

def main():
  parser = argparse.ArgumentParser(description='Web3Signer Voluntary Exits')
  parser.add_argument('--cl', type=str)
  parser.add_argument('--web3signer', type=str)
  parser.add_argument('--verify', type=bool, action=argparse.BooleanOptionalAction)
  parser.add_argument('pubkey', nargs='+')
  args = parser.parse_args()

  cl = args.cl
  web3signer = args.web3signer
  pubkeys = args.pubkey
  
  # Fetch fork data
  fork_response = requests.get(f"{cl}/eth/v1/beacon/states/finalized/fork")
  fork = fork_response.json()['data']

  # Fetch genesis data
  genesis_response = requests.get(f"{cl}/eth/v1/beacon/genesis").json()
  genesis_validators_root = genesis_response['data']['genesis_validators_root']

  # Fetch block data
  block_response = requests.get(f"{cl}/eth/v2/beacon/blocks/head")
  block_number = block_response.json()['data']['message']['slot']
  current_epoch = int(block_number) // 32

  if args.pubkey == ['auto']:
    pubkeys = requests.get(f"{web3signer}/api/v1/eth2/publicKeys").json()
  
  for pubkey in pubkeys:
    SignExitMessage(pubkey, cl, web3signer, fork,
                    genesis_validators_root, current_epoch,
                    args.verify)


if __name__ == "__main__":
  main()
