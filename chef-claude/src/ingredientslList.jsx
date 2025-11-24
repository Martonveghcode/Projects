export default function IngredientsList(props) {
    return(
        <ul ref={props.ref} className="ingredients-list" aria-live="polite">{props.ingredientsListItems}</ul>
    )
}