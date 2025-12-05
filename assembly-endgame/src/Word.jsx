import { nanoid } from "nanoid";

export default function Word({ word, guessedLetters }) {
    return (
        <section className="chips">
            {word.split("").map(letter => (
                <span key={nanoid()} className="word-p">
                    {guessedLetters.includes(letter) ? letter : ""}
                </span>
            ))}
        </section>
    );
}
