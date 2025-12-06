export default function NewGame(props) {
    return(
        <>
            {props.gameOver || props.gameWon ? <button className="newGame">New Game</button> : null}
        </>
    )
}