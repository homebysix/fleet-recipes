#!/bin/bash

# This uninstall script is taken from the Elgato Stream Deck Uninstaller Package:
# https://help.elgato.com/hc/en-us/articles/360028232731-Stream-Deck-Uninstall-Procedure-on-macOS

# unload the LaunchAgent
launchctl unload -w /Library/LaunchAgents/com.elgato.StreamDeck.plist > /dev/null 2>&1
launchctl unload -w $HOME/Library/LaunchAgents/com.elgato.StreamDeck.plist > /dev/null 2>&1

# kill the Stream Deck application if it was launched manually
killall "Stream Deck" > /dev/null 2>&1 || true

# delete previous Stream Deck app (as it may have different name)
rm -f /Library/LaunchAgents/com.elgato.StreamDeck.plist
rm -f $HOME/Library/LaunchAgents/com.elgato.StreamDeck.plist

# remove app
rm -rf "/Applications/Stream Deck.app"
rm -rf "/Applications/Elgato Stream Deck.app"

# remove STREAMDECKSHM
su - $USER -c "/bin/rm -rf ~/Library/Caches/STREAMDECKSHM"

# remove cache
su - $USER -c "/bin/rm -rf ~/Library/Caches/elgato/StreamDeck"
su - $USER -c "/bin/rm -rf ~/Library/Caches/com.elgato.StreamDeck"

# remove com.elgato.StreamDeck in Application Support (Profiles, HockeyApp)
su - $USER -c "/bin/rm -rf ~/Library/Application\ Support/com.elgato.StreamDeck"

# remove preferences
su - $USER -c "defaults delete com.elgato.StreamDeck"
su - $USER -c "/bin/rm -rf ~/Library/Preferences/com.elgato.StreamDeck.plist"

# remove logs
su - $USER -c "/bin/rm -rf ~/Library/Logs/StreamDeck"

# remove OBS related stuff
PLUGIN_NAME="StreamDeckPlugin"

OBS_PLUGINS_DIR_V2="$HOME/Library/Application Support/obs-studio/plugins"
rm -rf "$OBS_PLUGINS_DIR_V2/$PLUGIN_NAME.plugin"

OBS_PLUGINS_DIR="/Library/Application Support/obs-studio/plugins"
rm -rf "$OBS_PLUGINS_DIR/$PLUGIN_NAME"

exit 0