import { useState } from "react";

const LANGUAGE_OPTIONS = [
  { code: "en", label: "EN" },
  { code: "es", label: "ES" },
  { code: "fr", label: "FR" },
  { code: "de", label: "DE" },
];

const BASE_PROJECTS = [
  {
    id: "calendar",
    title: "Homework Calendar",
    summary: "Auto-assigns homework to class dates to avoid missed deadlines.",
    tech: ["React", "Automation"],
    links: {
      github: "https://github.com/Martonveghcode/calendar",
      live: "https://glittery-blini-4c6ea4.netlify.app",
    },
  },
  {
    id: "handwriting-pipeline",
    title: "Handwriting Formatting Pipeline",
    summary: "Cleans scanned notes, removes lines, and formats pages.",
    tech: ["Python", "Imaging"],
    links: {
      github: "https://github.com/Martonveghcode/Handwriting-formatting-pipeline",
    },
  },
  {
    id: "chef-claude",
    title: "Chef-Claude",
    summary: "Ingredient-based recipe generator using Google APIs.",
    tech: ["JavaScript", "APIs"],
    links: {
      github: "https://github.com/Martonveghcode/Projects/tree/main/chef-claude",
    },
  },
  {
    id: "react-blog",
    title: "React Blog",
    summary: "Blog that renders from data files without manual rebuilds.",
    tech: ["React", "Content automation"],
    links: {
      github: "https://github.com/Martonveghcode/Projects/tree/main/react-blog",
    },
  },
];

const BASE_PAPERS = [
  {
    id: "paper-1",
    title: "Paper slot #1",
    summary: "Placeholder for a research paper or essay (add PDF soon).",
    status: "Placeholder",
  },
  {
    id: "paper-2",
    title: "Paper slot #2",
    summary: "Reserved for a future publication or writeup.",
    status: "Placeholder",
  },
];

const BASE_EXPERIENCE = [
  {
    id: "bda",
    period: "2025",
    title: "Budapest Design Apartments - Intern",
    detail: "Client coordination and admin workflows.",
  },
  {
    id: "rcnp",
    period: "2024",
    title: "Real Club Nautico de Palma - Intern",
    detail: "Event logistics and on-site team support.",
  },
];

const translations = {
  en: {
    nav: { home: "Home", projects: "Projects", papers: "Papers", experience: "Experience" },
    heroTagline: "16-year-old developer", // keep concise per request
    heroSub: "Focused on practical builds and clean delivery.",
    aboutTitle: "Who I am",
    aboutBlurb:
      "Student developer with strong math/physics base, learning fast by shipping real tools. Multilingual and comfortable explaining what I build.",
    languagesTitle: "Languages",
    languagesList: [
      "Hungarian (native)",
      "English (fluent)",
      "Spanish (fluent)",
      "French (B2)",
      "Catalan (learning)",
    ],
    stackTitle: "What I use",
    stackCoreLabel: "Core",
    stackLearningLabel: "Learning",
    passionsTitle: "Passions",
    passionsList: ["Automation", "Productivity tooling", "Pure mathematics", "Canoe sprint & track"],
    githubTitle: "GitHub heatmap",
    projectsTitle: "Projects",
    papersTitle: "Papers",
    experienceTitle: "Experience",
    links: { live: "Live", github: "GitHub" },
    projects: {
      calendar: { summary: "Auto-assigns homework to class dates to avoid missed deadlines." },
      "handwriting-pipeline": { summary: "Cleans scanned notes, removes lines, and formats pages." },
      "chef-claude": { summary: "Ingredient-based recipe generator using Google APIs." },
      "react-blog": { summary: "Blog that renders from data files without manual rebuilds." },
    },
    papers: {
      "paper-1": { summary: "Placeholder for a research paper or essay (add PDF soon)." },
      "paper-2": { summary: "Reserved for a future publication or writeup." },
    },
    experience: {
      bda: { title: "Budapest Design Apartments - Intern", detail: "Client coordination and admin workflows." },
      rcnp: { title: "Real Club Nautico de Palma - Intern", detail: "Event logistics and on-site team support." },
    },
  },
  es: {
    nav: { home: "Inicio", projects: "Proyectos", papers: "Papers", experience: "Experiencia" },
    heroTagline: "Desarrollador de 16 anos",
    heroSub: "Enfocado en proyectos practicos y entregas limpias.",
    aboutTitle: "Quien soy",
    aboutBlurb:
      "Estudiante desarrollador con base fuerte en mates/fisica, aprendiendo rapido al lanzar herramientas reales. Multilingue y capaz de explicar lo que construyo.",
    languagesTitle: "Idiomas",
    languagesList: [
      "Hungaro (nativo)",
      "Ingles (fluido)",
      "Espanol (fluido)",
      "Frances (B2)",
      "Catalan (en aprendizaje)",
    ],
    stackTitle: "Que uso",
    stackCoreLabel: "Nucleo",
    stackLearningLabel: "Aprendiendo",
    passionsTitle: "Pasiones",
    passionsList: ["Automatizacion", "Productividad", "Matematicas puras", "Piraguismo y atletismo"],
    githubTitle: "Heatmap de GitHub",
    projectsTitle: "Proyectos",
    papersTitle: "Papers",
    experienceTitle: "Experiencia",
    links: { live: "Demo", github: "GitHub" },
    projects: {
      calendar: { summary: "Asigna tareas a fechas de clase para evitar retrasos." },
      "handwriting-pipeline": { summary: "Limpia notas escaneadas, quita lineas y maqueta paginas." },
      "chef-claude": { summary: "Generador de recetas segun ingredientes con APIs de Google." },
      "react-blog": { summary: "Blog que se renderiza desde datos sin reconstruccion manual." },
    },
    papers: {
      "paper-1": { summary: "Espacio reservado para un paper o ensayo (PDF pronto)." },
      "paper-2": { summary: "Reservado para una futura publicacion o articulo." },
    },
    experience: {
      bda: { title: "Budapest Design Apartments - Practicas", detail: "Coordinacion de clientes y flujos administrativos." },
      rcnp: { title: "Real Club Nautico de Palma - Practicas", detail: "Logistica de eventos y apoyo en sitio." },
    },
  },
  fr: {
    nav: { home: "Accueil", projects: "Projets", papers: "Papiers", experience: "Experience" },
    heroTagline: "Developpeur de 16 ans",
    heroSub: "Focalise sur des projets concrets et une livraison propre.",
    aboutTitle: "Qui je suis",
    aboutBlurb:
      "Etudiant developpeur avec une base solide en maths/physique, qui apprend vite en livrant des outils reels. Multilingue et a l'aise pour expliquer ce que je construis.",
    languagesTitle: "Langues",
    languagesList: [
      "Hongrois (natif)",
      "Anglais (courant)",
      "Espagnol (courant)",
      "Francais (B2)",
      "Catalan (en apprentissage)",
    ],
    stackTitle: "Ce que j'utilise",
    stackCoreLabel: "Noyau",
    stackLearningLabel: "En apprentissage",
    passionsTitle: "Passions",
    passionsList: ["Automatisation", "Outils de productivite", "Mathematiques pures", "Canoe-kayak et athletisme"],
    githubTitle: "Heatmap GitHub",
    projectsTitle: "Projets",
    papersTitle: "Papiers",
    experienceTitle: "Experience",
    links: { live: "Demo", github: "GitHub" },
    projects: {
      calendar: { summary: "Assigne les devoirs aux dates de cours pour eviter les retards." },
      "handwriting-pipeline": { summary: "Nettoie des notes scannees, retire les lignes et met en page." },
      "chef-claude": { summary: "Generateur de recettes selon les ingredients via les APIs Google." },
      "react-blog": { summary: "Blog rendu depuis des donnees sans reconstruction manuelle." },
    },
    papers: {
      "paper-1": { summary: "Emplacement reserve pour un papier ou essai (PDF bientot)." },
      "paper-2": { summary: "Reserve pour une future publication ou article." },
    },
    experience: {
      bda: { title: "Budapest Design Apartments - Stage", detail: "Coordination clients et flux administratifs." },
      rcnp: { title: "Real Club Nautico de Palma - Stage", detail: "Logistique d'evenements et support sur site." },
    },
  },
  de: {
    nav: { home: "Start", projects: "Projekte", papers: "Papers", experience: "Erfahrung" },
    heroTagline: "16-jahriger Entwickler",
    heroSub: "Fokus auf praktische Builds und klare Umsetzung.",
    aboutTitle: "Wer ich bin",
    aboutBlurb:
      "Schuler-Entwickler mit starker Mathe/Physik-Basis, lernt schnell durch reale Tools. Mehrsprachig und kann erklaren, was ich baue.",
    languagesTitle: "Sprachen",
    languagesList: [
      "Ungarisch (Muttersprache)",
      "Englisch (fließend)",
      "Spanisch (fließend)",
      "Franzosisch (B2)",
      "Katalanisch (lerne)",
    ],
    stackTitle: "Was ich nutze",
    stackCoreLabel: "Kern",
    stackLearningLabel: "Lerne",
    passionsTitle: "Leidenschaften",
    passionsList: ["Automatisierung", "Produktivitatstools", "Reine Mathematik", "Kanu und Leichtathletik"],
    githubTitle: "GitHub-Heatmap",
    projectsTitle: "Projekte",
    papersTitle: "Papers",
    experienceTitle: "Erfahrung",
    links: { live: "Live", github: "GitHub" },
    projects: {
      calendar: { summary: "Ordnet Hausaufgaben automatisch Kurstagen zu, um Verzug zu vermeiden." },
      "handwriting-pipeline": { summary: "Reinigt gescannte Notizen, entfernt Linien und formatiert Seiten." },
      "chef-claude": { summary: "Rezeptgenerator nach Zutaten mit Google-APIs." },
      "react-blog": { summary: "Blog rendert aus Daten ohne manuelles Neuaufbauen." },
    },
    papers: {
      "paper-1": { summary: "Platzhalter fur Paper oder Essay (PDF bald)." },
      "paper-2": { summary: "Reserviert fur eine spateren Veroffentlichung." },
    },
    experience: {
      bda: { title: "Budapest Design Apartments - Praktikum", detail: "Kundenkoordination und administrative Ablaufe." },
      rcnp: { title: "Real Club Nautico de Palma - Praktikum", detail: "Event-Logistik und Support vor Ort." },
    },
  },
};

const githubHeatmap = "https://ghchart.rshah.org/216e39/Martonveghcode";

const PAGES = ["home", "projects", "papers", "experience"];

function Nav({ language, onLanguageChange, page, onNavigate, copy }) {
  return (
    <header className="topbar">
      <div className="identity">
        <div className="initials">MV</div>
        <div>
          <p className="name">Marton Vegh</p>
        </div>
      </div>
      <nav className="nav-links">
        {PAGES.map((key) => (
          <button
            key={key}
            className={`nav-btn ${page === key ? "active" : ""}`}
            onClick={() => onNavigate(key)}
          >
            {copy.nav[key]}
          </button>
        ))}
      </nav>
      <div className="lang-switch">
        {LANGUAGE_OPTIONS.map((option) => (
          <button
            key={option.code}
            className={`chip ${language === option.code ? "chip-active" : ""}`}
            onClick={() => onLanguageChange(option.code)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </header>
  );
}

function Section({ title, children }) {
  return (
    <section className="section">
      <div className="section-head">
        <h2>{title}</h2>
        <div className="divider" />
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const [language, setLanguage] = useState("en");
  const [page, setPage] = useState("home");
  const copy = translations[language] ?? translations.en;

  const localizedProjects = BASE_PROJECTS.map((project) => {
    const override = copy.projects?.[project.id] ?? {};
    return { ...project, title: override.title ?? project.title, summary: override.summary ?? project.summary };
  });

  const localizedPapers = BASE_PAPERS.map((paper) => {
    const override = copy.papers?.[paper.id] ?? {};
    return { ...paper, title: override.title ?? paper.title, summary: override.summary ?? paper.summary };
  });

  const localizedExperience = BASE_EXPERIENCE.map((item) => {
    const override = copy.experience?.[item.id] ?? {};
    return { ...item, title: override.title ?? item.title, detail: override.detail ?? item.detail };
  });

  const renderHome = () => (
    <main className="layout">
      <section className="hero">
        <div className="hero-text">
          <p className="muted">{copy.heroTagline}</p>
          <h1>Marton Vegh</h1>
          <p className="lede">{copy.heroSub}</p>
        </div>
        <div className="hero-aside">
          <p className="muted">{copy.githubTitle}</p>
          <img className="heatmap" src={githubHeatmap} alt="GitHub heatmap" />
        </div>
      </section>

      <Section title={copy.aboutTitle}>
        <p className="muted">{copy.aboutBlurb}</p>
      </Section>

      <Section title={copy.languagesTitle}>
        <div className="menu">
          {copy.languagesList.map((item) => (
            <div key={item} className="menu-item">
              {item}
            </div>
          ))}
        </div>
      </Section>

      <Section title={copy.stackTitle}>
        <div className="grid two">
          <div>
            <h3>{copy.stackCoreLabel}</h3>
            <p className="muted">React | JavaScript | HTML/CSS</p>
          </div>
          <div>
            <h3>{copy.stackLearningLabel}</h3>
            <p className="muted">Python | C++</p>
          </div>
        </div>
      </Section>

      <Section title={copy.passionsTitle}>
        <div className="menu">
          {copy.passionsList.map((item) => (
            <div key={item} className="menu-item">
              {item}
            </div>
          ))}
        </div>
      </Section>
    </main>
  );

  const renderProjects = () => (
    <main className="layout single">
      <Section title={copy.projectsTitle}>
        <div className="list">
          {localizedProjects.map((project) => (
            <article key={project.id} className="list-row">
              <div>
                <p className="muted small">{project.tech.join(" / ")}</p>
                <h3>{project.title}</h3>
                <p className="muted">{project.summary}</p>
              </div>
              <div className="links">
                {project.links.live ? (
                  <a href={project.links.live} target="_blank" rel="noreferrer">
                    {copy.links.live}
                  </a>
                ) : null}
                <a href={project.links.github} target="_blank" rel="noreferrer">
                  {copy.links.github}
                </a>
              </div>
            </article>
          ))}
        </div>
      </Section>
    </main>
  );

  const renderPapers = () => (
    <main className="layout single">
      <Section title={copy.papersTitle}>
        <div className="list">
          {localizedPapers.map((paper) => (
            <article key={paper.id} className="list-row">
              <div>
                <p className="muted small">{paper.status}</p>
                <h3>{paper.title}</h3>
                <p className="muted">{paper.summary}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>
    </main>
  );

  const renderExperience = () => (
    <main className="layout single">
      <Section title={copy.experienceTitle}>
        <div className="list">
          {localizedExperience.map((item) => (
            <article key={item.id} className="list-row">
              <div>
                <p className="muted small">{item.period}</p>
                <h3>{item.title}</h3>
                <p className="muted">{item.detail}</p>
              </div>
            </article>
          ))}
        </div>
      </Section>
    </main>
  );

  const renderPage = () => {
    if (page === "projects") return renderProjects();
    if (page === "papers") return renderPapers();
    if (page === "experience") return renderExperience();
    return renderHome();
  };

  return (
    <div className="page">
      <Nav
        language={language}
        onLanguageChange={setLanguage}
        page={page}
        onNavigate={setPage}
        copy={copy}
      />
      {renderPage()}
      <footer className="footer">
        <div className="footer-info">
          <span>Marton Vegh</span>
          <span>Mallorca, Spain</span>
          <span>Email: <a href="mailto:martonvegh2009@gmail.com">martonvegh2009@gmail.com</a></span>
          <span>GitHub: <a href="https://github.com/Martonveghcode" target="_blank" rel="noreferrer">github.com/Martonveghcode</a></span>
        </div>
        <div className="footer-social">
          <a href="https://www.instagram.com/marton.alt" target="_blank" rel="noreferrer">Instagram</a>
          <a href="https://github.com/Martonveghcode" target="_blank" rel="noreferrer">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
