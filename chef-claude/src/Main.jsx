import React from "react"
import Recipe from "./recipe"
import IngredientsList from "./ingredientslList"

export default function Main() {
    const [isShown, setIsShown] = React.useState(false)

    
    const [ingredients, setIngredients] = React.useState([])

    const ingredientsListItems = ingredients.map(ingredient => (
        <li key={ingredient}>{ingredient}</li>
    ))

    function addIngredient(formData) {
        const newIngredient = formData.get("ingredient")
        setIngredients(prevIngredients => [...prevIngredients, newIngredient])
    }
    function handleShownRep() {
        setIsShown(!isShown)
    }
    

    return (
        <main>
            <form action={addIngredient} className="add-ingredient-form">
                <input
                    type="text"
                    placeholder="e.g. oregano"
                    aria-label="Add ingredient"
                    name="ingredient"
                />
                <button>Add ingredient</button>
            </form>
            <section>
                {ingredients.length > 0 ? <h2>Ingredients on hand:</h2> : null}
                <IngredientsList ingredientsListItems={ingredientsListItems}/>
                <div className="get-recipe-container"> 
                    <div>
                        {ingredients.length > 5 ? <h3>Ready for a recipe?</h3> : null}
                        {ingredients.length > 5 ?<p>Generate a recipe from your list of ingredients.</p> : null}
                    </div>
                    {ingredients.length > 5 ? <button onClick={handleShownRep}>Get a recipe</button> : null}
                </div> 
            </section>
            {isShown ? <Recipe/> : null}

        </main>
    )
}