import React, { useState, useEffect } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { emailToUUID } from '../lib/uuid-utils';
import * as m from "../paraglide/messages.js";

const API_BASE_URL = import.meta.env.PUBLIC_SERVER_URL;

interface EmailRegistrationComponentProps {}

const EmailRegistrationComponent: React.FC<EmailRegistrationComponentProps> = () => {
    const [email, setEmail] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setIsLoading(true);

        if (!email.trim()) {
            setError(m.email_error_required());
            setIsLoading(false);
            return;
        }

        try {
            // Generate deterministic UUID from email
            const uuid = await emailToUUID(email.trim());

            // Store the UUID in localStorage for consistency with other components
            localStorage.setItem('uuid', uuid);

            const response = await fetch(`${API_BASE_URL}/user/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'uuid': uuid
                },
                
            });

            if (response.ok) {
                // Redirect to instructions
                window.location.href = '/instructions';
            } else {
                const errorData = await response.json();
                console.error('Registration failed:', errorData);
                throw new Error(errorData.error || 'Registration failed. Please try again.');
            }

        } catch (error) {
            console.error('Registration error:', error);
            const errorMessage = error instanceof Error ? error.message : 'An error occurred. Please try again.';
            setError(errorMessage);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="text-center bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-8">
            <h3 className="text-2xl font-semibold mb-4">{m.email_ready_to_begin()}</h3>
            <p className="text-gray-600 mb-6">{m.email_provide_address()}</p>

            <form onSubmit={handleSubmit} className="max-w-md mx-auto">
                <div className="flex flex-col sm:flex-row gap-4 items-center justify-center">
                    <Input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder={m.email_placeholder()}
                        required
                        className="flex-1 px-4 py-3 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center sm:text-left"
                        disabled={isLoading}
                    />
                    <Button 
                        type="submit"
                        className="bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white px-8 py-3 rounded-lg text-lg font-medium transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-1 disabled:opacity-50 disabled:cursor-not-allowed"
                        disabled={isLoading}
                    >
                        {isLoading ? m.email_registering() : m.email_begin_study()}
                    </Button>
                </div>

                {error && (
                    <div className="text-red-600 text-sm mt-3">
                        {error}
                    </div>
                )}

                {isLoading && (
                    <div className="text-blue-600 text-sm mt-3">
                        <svg className="animate-spin h-5 w-5 mr-2 inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                        </svg>
                        {m.email_registering()}
                    </div>
                )}
            </form>
        </div>
    );
};

export default EmailRegistrationComponent;
