'''Tanaleer storage bot'''
import os
from sys import exit
from pathlib import Path
import slack
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter

ENV_PATH = Path('.') / '.env'
load_dotenv(dotenv_path = ENV_PATH)

APP = Flask(__name__)
SEA = SlackEventAdapter(
    os.environ["SIGNING_SECRET"], "/slack/events", APP)
CLIENT = slack.WebClient(token = os.environ["SLACK_TOKEN"])
BOT_ID = CLIENT.api_call("auth.test")['user_id']
VAULT_FILE = os.environ["VAULT_LOCATION"]

def fatal_error(desc: str) -> None:
    print(f"\033[31m[ERROR] {desc}\033[0m")
    CLIENT.chat_postMessage(
        channel = os.environ["BOT_CHANNEL"],
        text = f"*Taneleen has died unexpectedly. _Reason:_* {desc}"
    )
    exit(1)

def vault_help_msg() -> str:
    return """*_Taneleer\'s Vault_*
`/vault-help` - see help message
`/vault [channel] [+/-] [amount] [item]` - modify item value in given vault. Assumes `global` if no channel given, or if channel does not exist.
`/add-vault [channel]` - add vault with given name
`/show-vault [channel]` - show contents of given vault. Assumes `global` if no channel given. Sums all values if `*` given.
"""

def save_vault(new_vault) -> None:
    '''Give a new vault dictionary to be saved'''
    new_contents = ""

    for vault in new_vault:
        new_contents += f"$ {vault}\n"
        for item in new_vault[vault]:
            new_contents += f"~ {new_vault[vault][item]} {item}\n"

    with open(VAULT_FILE, "w", encoding = "utf-8") as vault:
        vault.write(new_contents.strip())

def parse_vault() -> dict:
    '''Parse vault file and return data as dictionary'''
    with open(VAULT_FILE, "r", encoding = "utf-8") as vault:
        contents = vault.readlines()

    vault_dict = {}
    current_vault = "global"
    for line in contents:
        lineform = line.strip().split()
        match lineform:
            case ["$", name]:
                current_vault = name
                vault_dict[current_vault] = {}
            case ["~", value, name]:
                vault_dict[current_vault][name] = int(value)
            case _:
                fatal_error("unrecognized formatting in vault file")

    return vault_dict

def vault_content_message(vault, name) -> str:
    '''Given a single vault, generates a message which gives vault contents'''
    final = f"_Vault *{name}* contains:_ "
    for item in vault:
        final += f"{vault[item]} {item}, "
    if len(vault) == 0:
        final = f"Vault *{name}* contains no items.  "
    return final[:-2]

def tally_vault_contents(vault) -> dict:
    '''Tally all the contents of multiple vaults'''
    tally_vault = {}
    for ind_vault in vault:
        for key in vault[ind_vault]:
            if key in tally_vault:
                tally_vault[key] += vault[ind_vault][key]
            else:
                tally_vault[key] = vault[ind_vault][key]
    return tally_vault

def return_cmd_error(message, user_id, channel_id):
    '''Quickly print and error'''
    CLIENT.chat_postEphemeral(
        user = user_id,
        channel = channel_id,
        text = message
    )

@APP.route("/slack/Vault/help", methods = ["POST"])
def vault_help():
    '''Display help message when /vault-help is called'''
    user_id, channel_id = request.form['user_id'], request.form['channel_id']
    CLIENT.chat_postEphemeral(
        user = user_id,
        channel = channel_id,
        text = vault_help_msg()
    )
    return Response(), 200


@APP.route("/slack/Vault/update", methods = ["POST"])
def vault_update():
    '''Modify values in the vault'''
    user_id, channel_id, msg_text =\
        request.form['user_id'], request.form['channel_id'], request.form['text']
    vault_contents = parse_vault()

    message_text = ""
    commands = msg_text.strip().split()
    if not commands:
        return_cmd_error("No values to modify. Try: `/vault +50gp`", user_id, channel_id)
        return Response(), 200

    channel = "global"
    if len(commands) == 1:
        if not commands[0][0].isdigit() and commands[0][0] not in ['+', '-']:
            return_cmd_error("No values to modify. Try: `/vault thomas -50gp`", user_id, channel_id)
            return Response(), 200
    if len(commands) in [2, 3, 4]:
        if len(commands[0]) == 1 or commands[0].isdigit():
            commands = ["".join(commands)]
        else:
            channel = commands[0]
            commands = ["".join(commands[1:])]

    channel = "global" if channel not in vault_contents else channel

    operation = "+"
    amount = -1
    name = "!"
    if commands[0][0] in ['+', '-']:
        operation = commands[0][0]
        commands[0] = commands[0][1:]

    num = ""
    item_name = ""
    for char in commands[0]:
        if char.isdigit():
            num += char
        elif char.isalpha():
            item_name += char
        else:
            return_cmd_error(f"Unrecognized character (`{char}`) in modification. \
Names must be alphabetical, values must be numerical.", user_id, channel_id)
            return Response(), 200

    if num:
        amount = int(num)
    if item_name:
        name = item_name

    if amount > 0 and name != "!":
        if name in vault_contents[channel]:
            if operation == "+":
                vault_contents[channel][name] += amount
            elif operation == "-":
                if vault_contents[channel][name] - amount < 0:
                    return_cmd_error(f"This action would reduce the value below zero. \
Try a value {vault_contents[channel][name]} or lower.", user_id, channel_id)
                    return Response(), 200
                vault_contents[channel][name] -= amount
        else:
            if operation == "+":
                vault_contents[channel][name] = amount
            elif operation == "-":
                return_cmd_error("You cannot reduce a value below 0.", user_id, channel_id)
                return Response(), 200
    else:
        return_cmd_error("You cannot reduce a value below 0. / No item name.", user_id, channel_id)
        return Response(), 200

    save_vault(vault_contents)

    message_text = f"Vault item *{name}* in vault `{channel}` was modified {operation}{amount} \
to a total of {vault_contents[channel][name]} {name}."
    CLIENT.chat_postEphemeral(
        user = user_id,
        channel = channel_id,
        text = message_text
    )


    return Response(), 200

@APP.route("/slack/Vault/show", methods = ["POST"])
def vault_show():
    '''Show contents of vault'''
    user_id, channel_id, msg_text =\
        request.form['user_id'], request.form['channel_id'], request.form['text']
    vault_contents = parse_vault()

    message_text = ""
    commands = msg_text.strip().split()
    match commands:
        case []:
            message_text = vault_content_message(vault_contents["global"], "global")
        case [name]:
            if name in vault_contents:
                message_text = vault_content_message(vault_contents[name], name)
            elif name == "*":
                message_text = vault_content_message(tally_vault_contents(vault_contents), "")
                message_text = "_Tally of *all vaults* contain" + message_text[18:]
                for vault in vault_contents:
                    message_text += "\n\t" + vault_content_message(vault_contents[vault], vault)
            else:
                vaults = "".join([f"`{name}`, " for name in vault_contents])[:-2]
                message_text = f"Vault *{name}* does not exist. Try: {vaults}."
        case _:
            message_text = "Unrecognized /show-vault pattern. Try: `/show-vault [channel]`, `/show-vault *`"

    CLIENT.chat_postEphemeral(
        user = user_id,
        channel = channel_id,
        text = message_text
    )

    return Response(), 200

@APP.route("/slack/Vault/add", methods = ["POST"])
def vault_add():
    '''Add a new vault channel'''
    user_id, channel_id, msg_text =\
        request.form['user_id'], request.form['channel_id'], request.form['text']
    vault_contents = parse_vault()

    message_text = ""
    name = msg_text.strip()
    if not name:
        message_text = "?You must give a new vault name. Try: `/add-vault [name]`"
    elif name in vault_contents:
        message_text = f"?Vault *{name}* already exists."
    elif " " in name or not name.isalpha():
        message_text = "?Non-alphabetical characters are not valid in vault names."
    else:
        vault_contents[name] = {}
        save_vault(vault_contents)
        message_text = f"User <@{user_id}> has created a new vault *{name}*."

    if message_text[0] == "?":
        CLIENT.chat_postEphemeral(
            user = user_id,
            channel = channel_id,
            text = message_text[1:]
        )
    else:
        CLIENT.chat_postMessage(
            channel = channel_id,
            text = message_text
        )

    return Response(), 200

def main() -> None:
    '''Main function'''
    APP.run(debug = True)

if __name__ == "__main__":
    main()
