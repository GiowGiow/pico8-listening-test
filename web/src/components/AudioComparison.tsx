import AudioPlayer, { RHAP_UI } from 'react-h5-audio-player';
import 'react-h5-audio-player/lib/styles.css';
import '../styles/audio-comparison.css'; 
import type { PairData } from '@/types/survey_types';
import * as m from "../paraglide/messages.js";
import { useState, useEffect } from 'react';

interface AudioComparisonProps {
  pair: PairData;
}

const AudioComparison: React.FC<AudioComparisonProps> = ({pair}) => {
  const [isMobile, setIsMobile] = useState(false);
  // Hide volume control on mobile devices
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    handleResize(); // Call on initial render

    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const customControlsSection = isMobile
    ? [RHAP_UI.MAIN_CONTROLS]
    : [RHAP_UI.VOLUME, RHAP_UI.MAIN_CONTROLS];

  return (
    <div className="audio-comparison">
      <div className="player-container flex items-center mb-4" style={{ flexDirection: 'row', alignItems: 'center' }}>        
        <div className="track-label mr-4 font-semibold text-gray-700" style={{ minWidth: 70 }}>{m.survey_track_1()}</div>
        <AudioPlayer
          src={pair.trackA}
          layout="horizontal-reverse"
          progressUpdateInterval={100}
          showJumpControls={false}
          autoPlay={false}
          preload="auto"
          customAdditionalControls={[]}
          customControlsSection={customControlsSection}
          style={{
            width: '70%',
            backgroundColor: '#f8f9fa',
            borderRadius: '8px',
            padding: '12px'
          }}
        />
      </div>

      <div className="player-container flex items-center mb-4" style={{ flexDirection: 'row', alignItems: 'center' }}>
        <div className="track-label mr-4 font-semibold text-gray-700" style={{ minWidth: 70 }}>{m.survey_track_2()}</div>
        <AudioPlayer
          src={pair.trackB}
          layout="horizontal-reverse"
          progressUpdateInterval={100}
          showJumpControls={false}
          autoPlay={false}
          preload="auto"
          customAdditionalControls={[]}
          customControlsSection={customControlsSection}
          style={{
            width: '70%',
            backgroundColor: '#f8f9fa',
            borderRadius: '8px',
            padding: '12px'
          }}
        />
      </div>
    </div>
  );
};

export default AudioComparison;