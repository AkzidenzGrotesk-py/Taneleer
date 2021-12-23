# Taneleer
Manage values in Slack. Made for D&amp;D.

You must host the app yourself, this can be done through [ngrok](https://ngrok.com/).

## Current Features (`/vault-help`)
### ***Taneleer\'s Vault***
`/vault-help` - see help message\
`/vault [channel] [+/-] [amount] [item]` - modify item value in given vault. Assumes `global` if no channel given, or if channel does not exist. `channel` argument must be surrounded by spaces, other arguments can be joined together. e.g. `/vault +1 potionOfHealing`\*. This pattern of `channel, +/-, amount, item` can be repeated on new lines to bulk append items.\
```perl
/vault +200 gp
thomas +100 gp
+200 sp
```
`/add-vault [channel]` - add vault with given name.\
`/show-vault [channel]` - show contents of given vault. Assumes `global` if no channel given. Sums all values if `*` given.\
`/confg-vault [config] [...]` - change the current configuration.\
→ `/confg-vault current` - display the current configuration.\
→ `/confg-vault zero [item]` - item will not be cleared when value reaches zero.\
→ `/confg-vault display [item] [display name] [...]` - item will now display as a different display name (which can contain spaces) when `/show-vault` is called.\
→ `/confg-vault display remove [item]` - item will no longer use display name\
→ `/confg-vault priorities [list priorities]` - set (not add) priorities in the order given\
`/-vault [...]` - vault extension commands, extension of `/vault`.\
→ `/-vault ri [channel] [item]` - set value of item in channel to 0.\
→ `/-vault rc [channel] [repeat]` - removes entire channel, must end with the channel name repeated for operation to complete.\
→ `/-vault note [item] [note] [...]` - add a note to an item which will display when `/show-vault` is called.\
→ `/-vault dnote [item]` - delete note at item.\
*It is recommended that item names are done in camelCase to keep consistency.\

## Todo
- Add alphabetical sorting to messages which contain lists of items
- Allow the categorization of items and the grouping of categorized items
- Add values using display value instead of ID (`/vault 5 "Map of France"`)
- ✓ Item priority levels, items will be displayed earlier/later in the /show-vault command
- ✓ Add multiple values at once, e.g. *removed*
- ✓ Consistent message style and format
- ✓ More configuration commands
- ✓ Add item descriptions
- ✓ Item display values (e.g. display `mapOfFrance` as `Map of France`)
