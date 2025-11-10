import { useState } from "react"

export default function Main() {
    let [ingredients, setIngredients] = useState([])

    

    ingredients = ingredients.map((x) => {
        return(<li key={x}>{x}</li>)
    })


    function handleSubmit(formData) {
        const ingredientsInForm = formData.get("ingredient")
        console.log(ingredientsInForm)
        setIngredients((prevIngredients) => [...prevIngredients, ingredientsInForm])



    
        }

    return(
        <main>
            <form className="add-ingredient-form" action={handleSubmit}>
                <input type="text" placeholder="e.g. aregano" name="ingredient"/>
                <button>+ ingredients</button>
            </form>
            <ul>
                {ingredients}
            </ul>
  
        </main>
        
    )
}