export default function IngredientsList(props) {
    return(
        <ul className="ingredients-list" aria-live="polite">{props.ingredientsListItems}</ul>
    )
}