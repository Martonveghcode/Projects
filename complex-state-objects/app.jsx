import { useState } from "react"



export default function App() {
    const [contact, setContact] = useState({
        firstName: "John",
        lastName: "Doe",
        phone: "+1 (212) 555-1212",
        email: "itsmyrealname@example.com",
        isFavorite: false
    })
    /**
     * Challenge: Fill in the values in the markup
     * using the properties of our state object above
     * (Ignore `isFavorite` for now)
     */

    function toggleFavorite() {
        console.log("Toggle Favorite")
        contact.isFavorite = !contact.isFavorite 
        console.log(contact.isFavorite)
        
    }

    return (
        <main>
            <article className="card">
                
                <div className="info">
                    <button
                        onClick={toggleFavorite}
                        aria-pressed={contact.isFavorite}
                        className="favorite-button"
                    >
                        
                    </button>
                    <h2 className="name">
                        {contact.firstName + " " +  contact.lastName}
                    </h2>
                    <p className="contact">{contact.phone}</p>
                    <p className="contact">{contact.email}</p>
                </div>

            </article>
        </main>
    )
}
