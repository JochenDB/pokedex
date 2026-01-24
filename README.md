# pokedex

python3 -m http.server 8000


curl -s 'https://pokeapi.co/api/v2/pokemon?limit=2000' | jq -r '
    .results
    | to_entries
    | map({(.value.name): (.key + 1)})
    | add
' > pokedex-map.json

https://api-v2.getcollectr.com/data/showcase/c0827d3e-732c-44dd-bf1b-c94bdcc74e3d?offset=0&limit=1500&unstackedView=true&rid=4b00a039-732b-40ef-9a71-539674c99666&username=
