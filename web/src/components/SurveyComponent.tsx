const API_BASE_URL = import.meta.env.PUBLIC_SERVER_URL

import React, { useEffect, useState } from 'react';
import axios from 'axios'
import type { PairData, SurveyResponse } from "../types/survey_types";
import { Button } from './ui/button';
import { RadioGroup, RadioGroupItem } from "./ui/radio-group";
import { Label } from './ui/label';
import AudioComparison from './AudioComparison'
import * as m from "../paraglide/messages.js";

const extractFilename = (url: string) => {
  // try {
  //   const path = new URL(url).pathname; // e.g. /audios/random/genai/1cjjud6.mp3
  //   // Remove leading slash and filename, keep directory path
  //   const parts = path.replace(/^\//, '').split('/');
  //   if (parts.length > 1) {
  //     parts[parts.length - 1] = '*';
  //     return parts.join('/');
  //   }
  //   return '*';
  // } catch {
  //   return '';
  // }
};

const SurveyComponent: React.FC = () => {
  const [uuid, setUuid] = useState<string>("");
  const [totalPairs, setTotalPairs] = useState(10);
  const [audioPairs, setAudioPairs] = useState<PairData[]>([]);
  const [currentPairIndex, setCurrentPairIndex] = useState(0);
  const [startTime, setStartTime] = useState(Date.now());
  const [isLastPair, setIsLastPair] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [shouldRedirect, setShouldRedirect] = useState(false);
  const [formData, setFormData] = useState<SurveyResponse>({
    track_A: '',
    track_B: '',
    human_perception_option: -1,
    song_recognition_option: -1,
    comments: '',
    is_last_response: false
  });
  const [pair, setPair] = useState<PairData>()

  // Computed values
  const isFirstPair = currentPairIndex === 0;

    // Fetch response function
  const tryFetchResponse = async (responseUuid: string) => {
    if (!responseUuid || isSubmitting) return;
    
    setIsSubmitting(true);
    try {
      console.log("Fetching response for UUID:", responseUuid);
      const response = await axios.get(`${API_BASE_URL}/response/${responseUuid}`);
      return response.data;
    } catch (error) {
      console.error("Error fetching response:", error);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  };

  // Initial setup effect
  useEffect(() => {
    const storedUuid = localStorage.getItem('uuid');
    if (!storedUuid) {
      setShouldRedirect(true);
      return;
    }
    setUuid(storedUuid);
  }, []);

  // Fetch pairs effect
  useEffect(() => {
    const fetchPairs = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/pairs/`, {
          headers: { uuid: localStorage.getItem('uuid')}
        });

        
        if (!response.data.pairs || response.data.pairs.length === 0) {
          window.location.href = '/register';
          return;
        }
        const pairs = response.data.pairs;
        setAudioPairs(pairs);
        setTotalPairs(pairs.length);
        setIsLastPair(currentPairIndex === pairs.length - 1);
        // Set initial pair when pairs are fetched
        if (pairs.length > 0) {
          const initialPair = pairs[0];
          setPair(initialPair);
        }
      } catch (error) {
        console.error('Error fetching PairData:', error);
      }
    };

    if (audioPairs.length === 0) {
      fetchPairs();
    }
  }, []);


  useEffect(() => {
    if (!pair?.response_uuid) return;

    // Fetch response and update formData
    const fetchResponse = async () => {
      const data = await tryFetchResponse(pair.response_uuid);
      
      setFormData({
        track_A: pair.trackA,
        track_B: pair.trackB,
        comments: data?.comments ?? "",
        human_perception_option: data?.human_perception_option ?? -1,
        song_recognition_option: data?.song_recognition_option ?? -1,
        is_last_response: currentPairIndex === totalPairs - 1,
      });
      setStartTime(Date.now());
    };

    fetchResponse();
  }, [pair?.response_uuid, currentPairIndex, totalPairs]);

  //Submit response function
  const submitSingleResponse = async () => {
    if (!uuid || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const response = await axios.post(
        `${API_BASE_URL}/response/submit`,
        {
          response: formData,
          time: Date.now() - startTime
        },
        {
          headers: { "x-response-uuid": pair?.response_uuid }
        }
      );
      return response.data;
    } catch (error) {
      console.error("Submission error:", error);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNext = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (currentPairIndex >= totalPairs - 1 || !isFormValid()) return;

    const submitted = await submitSingleResponse();
    if (!submitted) return;

    const nextIndex = currentPairIndex + 1;
    setCurrentPairIndex(nextIndex);
    setIsLastPair(nextIndex === totalPairs - 1);

    // Update pair and responseUuid for the next pair
    const nextPair = audioPairs[nextIndex];
    setPair(nextPair);

    // Scroll to top of the page
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Fetch and set response data for the next pair
    
    (async () => {
      const data = await tryFetchResponse(nextPair.response_uuid);
      console.log("Next pair data:", data);
      setFormData({
        track_A: nextPair.trackA,
        track_B: nextPair.trackB,
        comments: data?.comments ?? "",
        human_perception_option: data?.human_perception_option ?? -1,
        song_recognition_option: data?.song_recognition_option ?? -1,
        is_last_response: false,
      });
      setStartTime(Date.now());
    })();
  };

  const handlePrevious = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (currentPairIndex <= 0) return;

    const submitted = await submitSingleResponse();
    if (!submitted) return;

    const prevIndex = currentPairIndex - 1;
    setCurrentPairIndex(prevIndex);
    setIsLastPair(false);

    // Update pair and responseUuid for the previous pair
    const prevPair = audioPairs[prevIndex];
    setPair(prevPair);

    // Scroll to top of the page
    window.scrollTo({ top: 0, behavior: 'smooth' });

    // Fetch and set response data for the previous pair
    (async () => {
      const data = await tryFetchResponse(prevPair.response_uuid);
      console.log("Previous pair data:", data);
      setFormData({
          track_A: prevPair.trackA,
          track_B: prevPair.trackB,
          comments: data?.comments ?? "",
          human_perception_option: data?.human_perception_option ?? -1,
          song_recognition_option: data?.song_recognition_option ?? -1,
          is_last_response: false,
        });
        setStartTime(Date.now());
    })();
  };

  const handleSubmit = async (e: React.MouseEvent) => {
    e.preventDefault()

    try {
      
      const data = await submitSingleResponse()

      if (data) {
        localStorage.removeItem('surveyAnswers')

        window.location.href = '/register';
      }
    } catch (error) {
      console.error('Submission error:', error);
    }
  };

  // Helper function to check if form is valid
  const isFormValid = () => {
    return formData.human_perception_option !== -1 && formData.song_recognition_option !== -1;
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const {name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };



  if (shouldRedirect) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen w-full bg-slate-50 selection:bg-blue-200 px-4 py-8">
        <div className="w-full max-w-md p-6 sm:p-8 text-center bg-white rounded-lg shadow-xl">
          <h2 className="text-2xl font-semibold text-gray-700 mb-3">
            {m.survey_registration_required()}
          </h2>
          <p className="mb-6 text-gray-600">
            {m.survey_registration_message()}
          </p>
          <Button
            className="w-full py-3 text-lg"
            onClick={() => (window.location.href = '/')}
            id="home-redirect"
          >
            {m.survey_go_to_registration()}
          </Button>
        </div>
      </div>
    );
  }

  if (!pair) {
    return <div className="text-center mt-10">{m.survey_loading_pairs()}</div>;
  } else {
      return (
        <div className="survey-component max-w-4xl mx-auto p-6 bg-white shadow-md rounded-lg">
          <h2 className="text-2xl font-bold text-center mb-6">
            {m.survey_pair_of({ current: currentPairIndex + 1, total: totalPairs })}
          </h2>
          <p className='text-center mb-8'>
            {m.survey_listen_carefully()}
          </p>
          <p className='text-center mb-8'>
            {m.survey_answer_questions()}
          </p>

          <AudioComparison pair={pair}/>

          <form className="survey-form space-y-6" data-pair-id={currentPairIndex}>
            <input type="hidden" name="pairId" value={currentPairIndex} />

            <div className="form-group">
              <label className="block text-lg font-medium mb-2">
                {m.survey_ai_human_question()}
              </label>

              <RadioGroup
                className="flex flex-col gap-3"
                value={formData.human_perception_option.toString()}
                onValueChange={(value) => {
                  setFormData((prev) => ({
                    ...prev,
                    human_perception_option: Number(value),
                  }));
                }}
              >
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="0"
                    id="option-none"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="option-none" className="text-sm font-medium text-gray-900">
                    {m.survey_none_option()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="1"
                    id="option-track-A"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="option-track-A" className="text-sm font-medium text-gray-900">
                    {m.survey_track_1_option()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="2"
                    id="option-track-B"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="option-track-B" className="text-sm font-medium text-gray-900">
                    {m.survey_track_2_option()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="3"
                    id="option-both"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="option-both" className="text-sm font-medium text-gray-900">
                    {m.survey_both_option()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="4"
                    id="option-cannot-state"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="option-cannot-state" className="text-sm font-medium text-gray-900">
                    {m.survey_cannot_state_option()}
                  </Label>
                </div>
              </RadioGroup>
    
            </div>

            <div className="form-group">
              <label className="block text-lg font-medium mb-2">
                {m.survey_recognition_question()}
              </label>
            
              <RadioGroup
                className="flex flex-col gap-3"
                value={formData.song_recognition_option.toString()}
                onValueChange={(value) => {
                  setFormData((prev) => ({
                    ...prev,
                    song_recognition_option: Number(value),
                  }));
                }}
              >
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="0"
                    id="recognition-none"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="recognition-none" className="text-sm font-medium text-gray-900">
                    {m.survey_recognition_none()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="1"
                    id="recognition-track-a"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="recognition-track-a" className="text-sm font-medium text-gray-900">
                    {m.survey_recognition_track_1()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="2"
                    id="recognition-track-b"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="recognition-track-b" className="text-sm font-medium text-gray-900">
                    {m.survey_recognition_track_2()}
                  </Label>
                </div>
                <div className="flex items-center space-x-3">
                  <RadioGroupItem
                    value="3"
                    id="recognition-both"
                    className="h-4 w-4 mt-0.5"
                  />
                  <Label htmlFor="recognition-both" className="text-sm font-medium text-gray-900">
                    {m.survey_recognition_both()}
                  </Label>
                </div>
              </RadioGroup>
    
            </div>
    
            <div className="form-group">
              <label 
                className="block text-lg font-medium mb-2"
                htmlFor={`comments-${currentPairIndex}`}
              >
                {m.survey_comments_question()}
              </label>
              <textarea
                className="w-full p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" 
                id={`comments-${currentPairIndex}`} 
                name="comments" 
                rows={3}
                value={formData.comments}
                onChange={handleChange}
              ></textarea>
            </div>
            
            <div className="navigation-buttons flex justify-between items-center">
              
              {!isLastPair ? (
                <Button 
                type="button"
                className={`next-button px-6 py-2 rounded-lg ${
                  !isFormValid() || isSubmitting
                    ? 'bg-gray-400 text-gray-700 cursor-not-allowed'
                    : 'bg-blue-500 text-white hover:bg-blue-600'
                }`}
                  onClick={handleNext}
                  disabled={!isFormValid() || isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <svg className="animate-spin h-5 w-5 mr-2 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                      </svg>
                      {m.survey_loading()}
                    </>
                  ) : (
                    m.survey_next_pair()
                  )}
                </Button>
              ) : (
                <Button 
                  className={`submit-button px-6 py-2 rounded-lg ${
                    !isFormValid()
                      ? 'bg-gray-400 text-gray-700 cursor-not-allowed'
                      : 'bg-green-600 text-white hover:bg-green-600"'
                  }`}
                  type="button"  
                  onClick={handleSubmit}
                  disabled={!isFormValid()}
                >
                  {m.survey_submit()}
                </Button>
              )}
            </div>
          </form>
        </div>
      );
    };
  }

export default SurveyComponent;