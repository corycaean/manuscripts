#!/bin/bash

# enable compose key
export XKB_DEFAULT_OPTIONS="lv3:ralt_switch,compose:rctrl"

# The '--' is the critical part here
cage foot -- sh -c "cd /path/to/journal && ./run.sh; exec bash" &

wait $!
