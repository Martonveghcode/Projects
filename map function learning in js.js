const nums = [1, 2, 3, 4, 5]
// -->       [1, 4, 9, 16, 25]
// Your code here
const newNums = nums.map(function(num) {
    return num ** 2
})

console.log(newNums)


const names = ["alice", "bob", "charlie", "danielle"]
// -->        ["Alice", "Bob", "Charlie", "Danielle"]
// Your code here
const newNames = names.map(function (name) {
    return name.charAt(0).toUpperCase() + name.slice(1)
}) 
console.log(newNames)


const pokemon = ["Bulbasaur", "Charmander", "Squirtle"]
// -->          ["<p>Bulbasaur</p>", "<p>Charmander</p>", "<p>Squirtle</p>"]
// Your code here
const newpokemon = pokemon.map((pokemons) =>  `<p>${pokemons}</p>`)

console.log(newpokemon)

