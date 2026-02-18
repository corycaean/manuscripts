#!/bin/bash

# The '--' is the critical part here
cage foot -- sh -c "cd /path/to/journal && ./run.sh; exec bash" &

wait $!
