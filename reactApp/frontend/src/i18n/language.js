import { createContext, useContext } from "react";
import french from "./fr.json";
import spanish from "./es.json";
import german from "./de.json";

const translations = { fr: french, es: spanish, de: german };

export function readLanguage() {
  try {
    const saved = JSON.parse(localStorage.getItem("app_settings") || "{}")?.language;
    return Object.hasOwn(translations, saved) ? saved : "en";
  } catch {
    return "en";
  }
}

export function translate(language, text, values = {}) {
  const dictionary = Object.hasOwn(translations, language) ? translations[language] : undefined;
  const message = dictionary && Object.hasOwn(dictionary, text) ? dictionary[text] : text;
  return message.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match);
}

export const LanguageContext = createContext({ language: "en", t: (text) => text });
export function useLanguage() {
  return useContext(LanguageContext);
}
