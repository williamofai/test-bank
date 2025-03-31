#!/bin/bash
for i in {1..100}; do
    curl -s http://144.126.239.47:5000/api/balance/1234 > /dev/null &
done
wait
echo "Done!"
