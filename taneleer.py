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
VAULT_CONF = os.environ["VAULT_CONFG"]

def fatal_error(desc: str) -> None:
    print(f"\033[31m[ERROR] {desc}\033[0m")
    CLIENT.chat_postMessage(
        channel = os.environ["BOT_CHANNEL"],
        text = f"*Taneleen has died unexpectedly. _Reason:_* {desc}"
    )
    exit(1)

def vault_help_msg() -> str:
    '''Return the vault help message string'''
    return """*_Taneleer\'s Vault_*
`/vault-help` - see help message
`/vault [channel] [+/-] [amount] [item]` - modify item value in given vault. Assumes `global` if no channel given, or if channel does not exist. `channel` argument must be surrounded by spaces, other arguments can be joined together. e.g. `/vault +1 potionOfHealing`*.
`/add-vault [channel]` - add vault with given name.
`/show-vault [channel]` - show contents of given vault. Assumes `global` if no channel given. Sums all values if `*` given.
`/confg-vault [config] [...]` - change the current configuration.
\t`/confg-vault current` - display the current configuration.
\t`/confg-vault zero [item]` - item will not be cleared when value reaches zero.
\t`/confg-vault display [item] [display name] [...]` - item will now display as a different display name (which can contain spaces) when `/show-vault` is called.
`/-vault [...]` - vault extension commands, extension of `/vault`.
\t`/-vault ri [channel] [item]` - set value of item in channel to 0.
\t`/-vault rc [channel] [repeat]` - removes entire channel, must end with the channel name repeated for operation to complete.
\t`/-vault note [item] [note] [...]` - add a note to an item which will display when `/show-vault` is called.
\t`/-vault dnote [item]` - delete note at item
*It is recommended that item names are done in camelCase to keep consistency.
"""

def vault_save_config(new_config: dict) -> None:
    '''Save a new configuration'''
    new_confg_text = ""
    config_type = ""
    for item in new_config:
        new_confg_text += f"$ {item}\n"
        config_type = item
        for subs in new_config[item]:
            match config_type:
                case "display_names" | "item_notes":
                    new_confg_text += f"~ {subs} {new_config[item][subs]}\n"
                case "zero_exceptions":
                    new_confg_text += f"~ {subs}\n"

    with open(VAULT_CONF, "w", encoding = "utf-8") as vault_confg:
        vault_confg.write(new_confg_text[:-1])

def vault_config() -> dict:
    '''Get and return the vault configuration'''
    with open(VAULT_CONF, "r", encoding = "utf-8") as vault_confg:
        contents = vault_confg.readlines()

    confg = {
        "display_names" : {},
        "item_notes" : {},
        "zero_exceptions" : []
    }
    current = ""
    for line in contents:
        line = line.strip()
        if line[0] == "$":
            current = line[2:]
        elif line[0] == "~":
            match current:
                case "item_notes" | "display_names" as confg_set:
                    getter = line.split()
                    confg[confg_set][getter[1]] = " ".join(getter[2:])
                case "zero_exceptions":
                    getter = line.split()
                    confg["zero_exceptions"].append(getter[1])

    return confg

def save_vault(new_vault) -> None:
    '''Give a new vault dictionary to be saved'''
    new_contents = ""
    confg = vault_config()

    for vault in new_vault:
        new_contents += f"$ {vault}\n"
        for item in new_vault[vault]:
            item_val = new_vault[vault][item]
            if item_val == 0 and item not in confg["zero_exceptions"]:
                continue
            new_contents += f"~ {item_val} {item}\n"

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

def vault_content_message(vault, name, vault_confg) -> str:
    '''Given a single vault, generates a message which gives vault contents'''
    final = f"_Vault *{name}* contains:_ "
    for item in vault:
        txt_to_add = ""
        if item in vault_confg["display_names"]:
            txt_to_add += f"{vault[item]} {vault_confg['display_names'][item]}"
        else:
            txt_to_add += f"{vault[item]} {item}"

        if item in vault_confg["item_notes"]:
            txt_to_add = f"*{txt_to_add}* ({vault_confg['item_notes'][item]})"

        final += txt_to_add + ", "
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
        if len(commands[0]) == 1 or commands[0].isdigit() or commands[0][0] in ['+', '-']:
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
        if name == "!":
            return_cmd_error("Command missing item name.", user_id, channel_id)
        else:
            return_cmd_error("Missing a proper value.", user_id, channel_id)
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
    vault_confg = vault_config()
    vault_contents = parse_vault()

    message_text = ""
    commands = msg_text.strip().split()
    match commands:
        case []:
            message_text = vault_content_message(vault_contents["global"], "global", vault_confg)
        case [name]:
            if name in vault_contents:
                message_text = vault_content_message(vault_contents[name], name, vault_confg)
            elif name == "*":
                message_text = vault_content_message(tally_vault_contents(vault_contents), "", vault_confg)
                message_text = "_Tally of *all vaults* contain" + message_text[18:]
                for vault in vault_contents:
                    message_text += "\n\t" + vault_content_message(vault_contents[vault], vault, vault_confg)
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

@APP.route("/slack/Vault/extends", methods = ["POST"])
def vault_extension_cmds():
    '''Handles extension commands'''
    user_id, channel_id, msg_text =\
        request.form['user_id'], request.form['channel_id'], request.form['text']
    command = msg_text.strip().split()
    cur_vault = parse_vault()
    cur_config = vault_config()
    message_text = ""

    if len(command) < 1:
        return_cmd_error("This command requires arguments.", user_id, channel_id)
        return Response(), 200

    match command[0]:
        case "ri":
            if len(command) < 3:
                return_cmd_error("Removing an item requires more arguments.", user_id, channel_id)
                return Response(), 200
            if command[1] in cur_vault:
                if command[2] in cur_vault[command[1]]:
                    cur_vault[command[1]][command[2]] = 0
                    message_text = f"?The value of `{command[2]}` in `{command[1]}` has been set to 0"
                else:
                    message_text = "?That item does not exist in that channel"
            else:
                message_text = "?That channel does not exist."
        case "rc":
            if len(command) < 3:
                return_cmd_error("Removing a channel requires more arguments.", user_id, channel_id)
                return Response(), 200
            if command[1] in cur_vault:
                if command[2] == command[1]:
                    del cur_vault[command[1]]
                    message_text = f"User <@{user_id}> has permanently deleted the channel *{command[1]}*."
                else:
                    message_text = f"?You must repeat the channel name for the deletion operation."
            else:
                message_text = "?That channel does not exist."
        case "note":
            if len(command) < 3:
                return_cmd_error("Setting a note for a certain item requires more arguments.", user_id, channel_id)
                return Response(), 200

            cur_config["item_notes"][command[1]] = " ".join(command[2:])
            message_text = f"?Item `{command[1]}` now has a note: _{cur_config['item_notes'][command[1]]}_"
        case "dnote":
            if len(command) < 2:
                return_cmd_error("Deleting a note for a certain item requires more arguments.", user_id, channel_id)
                return Response(), 200

            if command[1] in cur_config["item_notes"]:
                del cur_config["item_notes"][command[1]]
                message_text = f"?Item `{command[1]}` no longer has a note."
            else:
                message_text = f"?That item does not have a note."

    save_vault(cur_vault)
    vault_save_config(cur_config)

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



@APP.route("/slack/Vault/config", methods = ["POST"])
def vault_updt_config():
    user_id, channel_id, msg_text =\
        request.form['user_id'], request.form['channel_id'], request.form['text']
    command = msg_text.split()
    config = vault_config()
    message_text = ""

    if len(command) < 1:
        return_cmd_error("This command requires arguments.", user_id, channel_id)
        return Response(), 200

    match command[0]:
        case "current":
            disp_names = "".join([
                f"`{iden}` -> \"{config['display_names'][iden]}\", "
                for iden in config["display_names"]
            ])[:-2]
            zero_excp = "".join([
                f"`{excpt}`, "
                for excpt in config["zero_exceptions"]
            ])[:-2]
            message_text = f"_*Current Taneleer Configuration*_\
                    \n*Display names (`display`):* {disp_names}\n*Zero exceptions (`zero`):* {zero_excp}"
        case "zero":
            if len(command) < 2:
                return_cmd_error("Editing the `zero` field of \
the configuration requires more arguments.", user_id, channel_id)
                return Response(), 300
            config["zero_exceptions"].append(command[1])
            message_text = f"Items with name `{command[1]}` \
will no longer clear when their value reaches 0."
        case "display":
            if len(command) < 3:
                return_cmd_error("Editing the `display` field of \
the configuration requires more arguments.", user_id, channel_id)
                return Response(), 300
            if command[1] == "remove":
                if command[2] in config["display_names"]:
                    del config["display_names"][command[2]]
                    message_text = f"Items with name `{command[2]}` will display as they are when /show-vault"
                else:
                    return_cmd_error("Removing a display field requires for it to exist.", user_id, channel_id)
                    return Response(), 300
            else:
                config["display_names"][command[1]] = " ".join(command[2:])
                message_text = f"Items with name `{command[1]}` will now \
display as `{config['display_names'][command[1]]}` when /show-vault"

    vault_save_config(config)
    CLIENT.chat_postEphemeral(
        user = user_id,
        channel = channel_id,
        text = message_text
    )
    return Response(), 200

def main() -> None:
    '''Main function'''
    APP.run(debug = True)

if __name__ == "__main__":
    main()
