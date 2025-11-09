import { useState } from "react"

export default function Main() {
    let [ingredients, setIngredients] = useState([])

    

    ingredients = ingredients.map((x) => {
        return(<li key={x}>{x}</li>)
    })


    function handleSubmit(event) {


    
        console.log(ingredients)
        event.preventDefault()
        const formData = new FormData(event.currentTarget)
        const newIngredient = formData.get("ingredient")
        setIngredients(prevIngredients => [...prevIngredients, newIngredient])
        
        console.log(ingredients)


    }

    return(
        <main>
            <form className="add-ingredient-form" onSubmit={handleSubmit}>
                <input type="text" placeholder="e.g. aregano" name="ingredient"/>
                <button>+ ingredients</button>
            </form>
            <ul>
                {ingredients}
            </ul>
  
        </main>
        
    )
}