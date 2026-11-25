import React from 'react';
import * as m from "../paraglide/messages.js";
import LanguageSwitcher from './LanguageSwitcher';
interface NavbarProps {
  currentPath: string;
}

const Navbar: React.FC<NavbarProps> = ({ currentPath }) => {
  return (
    <nav className="bg-white shadow-sm dark:bg-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center gap-6">
            <a href="/" className="text-xl font-semibold text-gray-900 dark:text-white">
              Humanness Percept
            </a>
            <div className="hidden sm:ml-6 sm:flex sm:flex gap-6">
              <a
                href="/"
                className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-300 inline-flex items-center px-1 pt-1 border-b-2 text-base font-medium ${
                  currentPath === '/' ? 'border-blue-500 text-blue-600' : ''
                }`}
              >
                {m.navbar_home()}
              </a>
              {/* <a
                href="/about"
                className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-300 inline-flex items-center px-1 pt-1 border-b-2 text-base font-medium ${
                  currentPath === '/about' ? 'border-blue-500 text-blue-600' : ''
                }`}
              >
                About
              </a>
              <a
                href="/contact"
                className={`border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-300 inline-flex items-center px-1 pt-1 border-b-2 text-base font-medium ${
                  currentPath === '/contact' ? 'border-blue-500 text-blue-600' : ''
                }`}
              >
                Contact
              </a> */}
            </div>
          </div>
          <div className="flex items-center">
            <LanguageSwitcher />
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;