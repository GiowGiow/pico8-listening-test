import React, { useState, useEffect } from 'react';
import { locales, getLocale, setLocale } from "../paraglide/runtime.js";

const LanguageSwitcher: React.FC = () => {
  const [currentLocale, setCurrentLocale] = useState<string>('pt-BR');

  useEffect(() => {
    try {
      const locale = getLocale();
      setCurrentLocale(locale);
    } catch (error) {
      console.warn('Could not get locale:', error);
      setCurrentLocale('pt-BR');
    }
  }, []);

  const handleLocaleChange = (newLocale: string) => {
    // Reload page to apply new locale
    setCurrentLocale(newLocale);
    setLocale(newLocale);
  };

  return (
    <select
      onChange={(e) => handleLocaleChange(e.target.value)}
      value={currentLocale}
      className="ml-4 p-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-600"
    >
      {locales.map((lang) => (
        <option key={lang} value={lang}>
          {lang === 'pt-BR' ? 'Português' : 'English'}
        </option>
      ))}
    </select>
  );
};

export default LanguageSwitcher;