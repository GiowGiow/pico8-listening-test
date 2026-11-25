import { useEffect, useState } from 'react';
import type { UserData } from '../types/survey_types';
import { Button } from './ui/button';
import { Input } from './ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Separator } from './ui/separator';
import axios from 'axios';
import ChevronDownIcon from './ui/chevron-down-icon';
import * as m from "../paraglide/messages.js";

// Assuming PUBLIC_SERVER_URL is correctly defined in your environment
const API_BASE_URL = import.meta.env.PUBLIC_SERVER_URL;

const getExperienceLevelMap = () => ({
  "-1": m.auth_choose_option(),
  "0": m.auth_less_than_year(),
  "1": m.auth_one_to_five_years(),
  "2": m.auth_five_to_ten_years(),
  "3": m.auth_over_ten_years(),
});

const getLanguageOptions = () => [
  { value: '', label: m.auth_select_language() },
  { value: 'english', label: m.language_english() },
  { value: 'spanish', label: m.language_spanish() },
  { value: 'french', label: m.language_french() },
  { value: 'german', label: m.language_german() },
  { value: 'portuguese', label: m.language_portuguese() },
  { value: 'mandarin', label: m.language_mandarin() },
  { value: 'hindi', label: m.language_hindi() },
  { value: 'arabic', label: m.language_arabic() },
  { value: 'japanese', label: m.language_japanese() },
  { value: 'russian', label: m.language_russian() },
  { value: 'korean', label: m.language_korean() },
  { value: 'italian', label: m.language_italian() },
  { value: 'other', label: m.language_other() },
];

interface AuthComponentProps {
  pageTitle?: string;
}

const AuthComponent: React.FC<AuthComponentProps> = ({ pageTitle }) => {
  const [age, setAge] = useState<number | string>('');
  const [language, setLanguage] = useState<string>('');
  const [practical_experience, setPracticalExperience] = useState<number>(-1);
  const [formal_experience, setFormalExperience] = useState<number>(-1);
  const [uuid, setUuid] = useState<string>('');
  const [showForm, setShowForm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [knows_ai_music, setKnowsAiMusic] = useState<boolean>(false);

  const experienceLevelMap = getExperienceLevelMap();
  const languageOptions = getLanguageOptions();

  useEffect(() => {
    const storedUuid = localStorage.getItem('uuid');
    if (storedUuid) {
      setUuid(storedUuid);
      setShowForm(true);
    } else {
      setShowForm(false);
    }
  }, []);

  const handleAgeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    
    // Allow empty input
    if (val === '') {
      setAge('');
      return;
    }
    
    // Parse as number and validate
    const numVal = parseInt(val, 10);
    
    // Only allow valid numbers within range
    if (!isNaN(numVal) && numVal >= 0 && numVal <= 120) {
      setAge(numVal);
    }
    // If invalid, don't update the state (keeps previous valid value)
  };

  const handleRegister = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsLoading(true);

    if (age === '' || Number(age) < 0 || Number(age) > 120 || language === '' || formal_experience === -1 || practical_experience === -1) {
      setError(m.auth_fill_all_fields());
      setIsLoading(false);
      return;
    }
    try {
      const newUserData: UserData = {
        age: Number(age),
        language: language,
        formal_experience: formal_experience,
        practical_experience: practical_experience,
        knows_ai_music: knows_ai_music,
      };

      const response = await axios.put(
        `${API_BASE_URL}/user/update`,
        newUserData,
        { headers: { uuid: uuid } }
      );
      const data = response.data;

      if (data) {
        localStorage.removeItem('uuid');
        window.location.href = '/thank-you';
      } else {
        setError(m.auth_registration_failed());
      }
    } catch (err) {
      console.error('Register error:', err);
      setError(
        err instanceof Error ? err.message : m.auth_unknown_error()
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (!showForm) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen w-full bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
        <div className="w-full max-w-md p-8 bg-white rounded-xl shadow-2xl text-center transition-all duration-300 ease-in-out transform hover:scale-105">
          <h2 className="text-3xl font-extrabold text-gray-800 mb-4">
            {m.auth_action_required()}
          </h2>
          <p className="mb-8 text-lg text-gray-600 leading-relaxed">
            {m.auth_complete_survey_message()}
          </p>
          <Button
            className="w-full py-3 text-lg font-semibold bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-lg shadow-md hover:from-blue-600 hover:to-indigo-700 transition-all duration-200"
            onClick={() => (window.location.href = '/survey')}
            id="survey-redirect"
          >
            {m.auth_take_survey_now()}
          </Button>
        </div>
      </div>
    );
  }

  const currentLanguageLabel = languageOptions.find(opt => opt.value === language)?.label || m.auth_select_language();

  return (
    <div className="min-h-screen w-full bg-gradient-to-br from-blue-50 to-indigo-100 flex flex-col items-center justify-center p-4 sm:p-8">
      {pageTitle && (
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-gray-800 mb-8 text-center drop-shadow-md">
          {pageTitle}
        </h1>
      )}
      <div className="w-full max-w-6xl bg-white rounded-lg shadow-xl p-6 sm:p-8">
        <div className="mb-6 text-center">
          <h2 className="text-3xl font-bold text-gray-800">
            {m.auth_demographic_survey()}
          </h2>
          <p className="text-gray-600 mt-3 leading-relaxed">
            {m.auth_thank_you_participating()}
          </p>
        </div>
        <div className="mb-8 text-sm text-gray-700 leading-relaxed bg-blue-50 p-4 rounded-lg border border-blue-200">
          <p className="mb-3">
            {m.auth_anonymous_participation()}
          </p>
          <ul className="list-disc list-outside pl-5 space-y-2 marker:text-blue-500 text-gray-700">
            <li><strong className="text-gray-800">{m.auth_your_age()}</strong></li>
            <li><strong className="text-gray-800">{m.auth_your_native_language()}</strong></li>
            <li>
              <strong className="text-gray-800">{m.auth_your_musical_experience()}</strong>
              <ul className="list-[circle] list-outside pl-6 mt-2 space-y-1 text-gray-600">
                <li><strong className="font-semibold text-gray-700">{m.auth_formal_experience_label()}:</strong> {m.auth_formal_experience_desc()}</li>
                <li><strong className="font-semibold text-gray-700">{m.auth_practical_experience_label()}:</strong> {m.auth_practical_experience_desc()}</li>
              </ul>
            </li>
          </ul>
          <p className="text-xs text-gray-500 mt-6 text-center italic">
            {m.auth_anonymous_disclaimer()}
          </p>
        </div>
        <Separator className="my-8 bg-gray-200 h-0.5" />
        <form
          onSubmit={handleRegister}
          className="space-y-7"
        >
          {error && (
            <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded-lg relative text-center" role="alert">
              <span className="block sm:inline">{error}</span>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-7">
            <div className="space-y-2">
              <label htmlFor="age" className="block text-sm font-medium text-gray-800">{m.auth_age_label()}</label>
              <Input
                id="age"
                name="age"
                type="number"
                className="w-full border-gray-300 rounded-md shadow-sm focus:border-blue-500 focus:ring-blue-500 p-2.5"
                placeholder={m.auth_age_placeholder()}
                value={age}
                onChange={handleAgeChange}
                required min={0} max={120}
                inputMode="numeric"
                pattern="[0-9]*"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="language" className="block text-sm font-medium text-gray-800">{m.auth_native_language_label()}</label>
              <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" className="w-full flex justify-between items-center text-gray-700 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 min-h-[2.75rem]">
                    <span className="truncate">{currentLanguageLabel}</span>
                    <ChevronDownIcon className="ml-2 h-4 w-4 opacity-60 flex-shrink-0" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent 
                  className="w-[var(--radix-dropdown-menu-trigger-width)] max-h-80 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg py-2 z-[9999]"
                  align="start"
                  sideOffset={4}
                  avoidCollisions={true}
                  sticky="always"
                >
                  <DropdownMenuLabel className="px-4 py-3 text-gray-500 font-medium text-sm">{m.auth_select_language()}</DropdownMenuLabel>
                  <DropdownMenuSeparator className="border-t border-gray-200" />
                  <DropdownMenuRadioGroup value={language} onValueChange={setLanguage}>
                    {languageOptions.map((option) => (
                      option.value === '' && option.label === m.auth_select_language() ? null : (
                        <DropdownMenuRadioItem 
                          key={option.value} 
                          value={option.value} 
                          className="px-4 py-3 text-base text-gray-700 hover:bg-slate-100 focus:bg-blue-50 cursor-pointer data-[highlighted]:bg-blue-50"
                        >
                          {option.label}
                        </DropdownMenuRadioItem>
                      )
                    ))}
                  </DropdownMenuRadioGroup>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
          {/* Musical Experience */}
          <div>
            <label className="block text-base font-bold text-gray-800 mb-4">{m.auth_musical_experience_label()}</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-7">
              <div className="space-y-2">
                <label htmlFor="formal_experience" className="block text-sm font-medium text-gray-800">{m.auth_formal_experience_label()}</label>
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" className="w-full flex justify-between items-center text-gray-700 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 min-h-[2.75rem]">
                      <span className="truncate">{experienceLevelMap[String(formal_experience) as keyof typeof experienceLevelMap]}</span>
                      <ChevronDownIcon className="ml-2 h-4 w-4 opacity-60 flex-shrink-0" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent 
                    className="w-[var(--radix-dropdown-menu-trigger-width)] bg-white border border-gray-200 rounded-lg shadow-lg py-2 z-[9999]"
                    align="start"
                    sideOffset={4}
                    avoidCollisions={true}
                    sticky="always"
                  >
                    <DropdownMenuLabel className="px-4 py-3 text-gray-500 font-medium text-sm">{m.auth_formal_experience_label()}</DropdownMenuLabel>
                    <DropdownMenuSeparator className="border-t border-gray-200" />
                    <DropdownMenuRadioGroup value={String(formal_experience)} onValueChange={(value) => setFormalExperience(Number(value))}>
                      {Object.entries(experienceLevelMap).filter(([key]) => key !== "-1").map(([value, label]) => (
                        <DropdownMenuRadioItem 
                          key={`formal-${value}`} 
                          value={value} 
                          className="px-4 py-3 text-base text-gray-700 hover:bg-slate-100 focus:bg-blue-50 cursor-pointer data-[highlighted]:bg-blue-50"
                        >
                          {label}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
              <div className="space-y-2">
                <label htmlFor="practical_experience" className="block text-sm font-medium text-gray-800">{m.auth_practical_experience_label()}</label>
                <DropdownMenu modal={false}>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" className="w-full flex justify-between items-center text-gray-700 border-gray-300 rounded-md shadow-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 p-2.5 min-h-[2.75rem]">
                      <span className="truncate">{experienceLevelMap[String(practical_experience) as keyof typeof experienceLevelMap]}</span>
                      <ChevronDownIcon className="ml-2 h-4 w-4 opacity-60 flex-shrink-0" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent 
                    className="w-[var(--radix-dropdown-menu-trigger-width)] bg-white border border-gray-200 rounded-lg shadow-lg py-2 z-[9999]"
                    align="start"
                    sideOffset={4}
                    avoidCollisions={true}
                    sticky="always"
                  >
                    <DropdownMenuLabel className="px-4 py-3 text-gray-500 font-medium text-sm">{m.auth_practical_experience_label()}</DropdownMenuLabel>
                    <DropdownMenuSeparator className="border-t border-gray-200" />
                    <DropdownMenuRadioGroup value={String(practical_experience)} onValueChange={(value) => setPracticalExperience(Number(value))}>
                      {Object.entries(experienceLevelMap).filter(([key]) => key !== "-1").map(([value, label]) => (
                        <DropdownMenuRadioItem 
                          key={`practical-${value}`} 
                          value={value} 
                          className="px-4 py-3 text-base text-gray-700 hover:bg-slate-100 focus:bg-blue-50 cursor-pointer data-[highlighted]:bg-blue-50"
                        >
                          {label}
                        </DropdownMenuRadioItem>
                      ))}
                    </DropdownMenuRadioGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
            <Separator className="my-6 bg-gray-200 h-0.5" />
            <div>
              <label className="flex items-center mt-4 font-bold text-gray-800">
                {m.auth_ai_music_question()}
              </label>
              <label className="flex items-center mt-2 italic text-gray-700">
                {m.auth_ai_music_question_desc()}
              </label>
              <br />
          
              <label className="flex items-center mt-2">
                <input
                  type="checkbox"
                  checked={knows_ai_music}
                  onChange={(e) => setKnowsAiMusic(e.target.checked)}
                  className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  {m.auth_familiar_ai_music()}
                </span>
              </label>
            </div>
          </div>
          <Button
            type="submit"
            className="w-full py-3 text-lg font-semibold bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg shadow-lg hover:from-green-600 hover:to-green-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-500 focus-visible:ring-offset-2 disabled:opacity-70 transition-all duration-200"
            disabled={isLoading}
          >
            {isLoading ? m.auth_registering() : m.auth_register()}
          </Button>
        </form>

        {/* Contact Information Section */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="text-center">
            {/* UUID Token Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">
                {m.auth_unique_token()}
              </h3>
              <div className="bg-gray-100 border border-gray-300 rounded-lg p-4 mx-auto max-w-md">
                <code className="text-lg font-mono text-gray-800 break-all">
                  {uuid}
                </code>
              </div>
              <div className="mt-4 text-sm text-gray-800 space-y-2">
                <p className="font-medium text-black">{m.auth_token_usage()}</p>
                <ul className="text-left max-w-md mx-auto space-y-1">
                  <li>• {m.auth_token_crowd_worker()}</li>
                  <li>• {m.auth_token_contact()}</li>
                </ul>
              </div>
            </div>

            {/* Divider */}
            <Separator className="mt-8 pt-6 border-t border-gray-200" />

            {/* Questions or Comments Section */}
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">
                {m.auth_questions_comments()}
              </h3>
              <p className="text-sm text-gray-700 mb-3">
                {m.auth_contact_message()}
              </p>
              <a 
                href="mailto:humanness_percept@uai.science" 
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline transition-colors duration-200"
              >
                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"></path>
                  <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"></path>
                </svg>
                humanness_percept@uai.science
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthComponent;