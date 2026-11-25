export interface SurveyResponse {
    track_A: string;
    track_B: string;
    human_perception_option: number;
    song_recognition_option: number;
    comments: string;
    is_last_response: boolean;
}

export interface UserData {
    age: number;
    practical_experience: number;
    formal_experience: number;
    language: string;
    knows_ai_music: boolean;
}

export interface PairData {
    response_uuid: string;
    trackA: string;
    trackB: string;
}