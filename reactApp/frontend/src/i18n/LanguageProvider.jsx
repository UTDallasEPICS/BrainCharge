import { useEffect, useMemo, useState } from "react";
import { LanguageContext, readLanguage, translate } from "./language.js";

export default function LanguageProvider({ children }) {
  const [language, setLanguage] = useState(readLanguage);

  useEffect(() => {
    const sync = () => setLanguage(readLanguage());
    window.addEventListener("settings-updated", sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener("settings-updated", sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  const value = useMemo(() => ({ language, t: (text, values) => translate(language, text, values) }), [language]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
