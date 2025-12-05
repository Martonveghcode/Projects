export default function NewGame(props) {
    return(
        <>
            {props.gameOver ? <button className="newGame">New Game</button> : null}
        </>
    )
}