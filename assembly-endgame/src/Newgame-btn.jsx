export default function NewGame({ gameOver, gameWon, onNewGame }) {
    if (!gameOver && !gameWon) {
        return null
    }

    return (
        <>
            <button onClick={onNewGame} className="newGame">
                New Game
            </button>
        </>
    )
}
