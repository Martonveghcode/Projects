export default function Chips({ chips }) {
    return (
        <>
            <section className="chips">
                {chips.map(chip => (
                    <div
                        className={`languages-div${chip.lost ? " lost" : ""}`}
                        key={chip.id}
                        style={{ background: chip.backgroundColor }}
                    >
                        <p className="languages-p" style={{ color: chip.color }}>
                            {chip.name}
                        </p>
                    </div>
                ))}
                
            </section>
        </>
    )
}
