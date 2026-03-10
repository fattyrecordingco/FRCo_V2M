#pragma once

#include <juce_audio_processors/juce_audio_processors.h>

class VINSPluginAudioProcessor final : public juce::AudioProcessor
{
public:
    VINSPluginAudioProcessor();
    ~VINSPluginAudioProcessor() override;

    void prepareToPlay(double sampleRate, int samplesPerBlock) override;
    void releaseResources() override;
    bool isBusesLayoutSupported(const BusesLayout& layouts) const override;
    void processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&) override;

    juce::AudioProcessorEditor* createEditor() override;
    bool hasEditor() const override { return true; }

    const juce::String getName() const override { return JucePlugin_Name; }
    bool acceptsMidi() const override { return true; }
    bool producesMidi() const override { return true; }
    bool isMidiEffect() const override { return false; }
    double getTailLengthSeconds() const override { return 0.0; }

    int getNumPrograms() override { return 1; }
    int getCurrentProgram() override { return 0; }
    void setCurrentProgram(int) override {}
    const juce::String getProgramName(int) override { return {}; }
    void changeProgramName(int, const juce::String&) override {}

    void getStateInformation(juce::MemoryBlock& destData) override;
    void setStateInformation(const void* data, int sizeInBytes) override;

private:
    void emitVoiceControllerMidi(const juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages);
    float estimateEnvelope(const juce::AudioBuffer<float>& buffer) const;
    float estimateBrightness(const juce::AudioBuffer<float>& buffer) const;
    float estimateFrequency(const juce::AudioBuffer<float>& buffer) const;

    juce::AudioProcessorValueTreeState parameters;
    double currentSampleRate = 44100.0;
    bool gateOpen = false;
    int lastMidiNote = -1;
    int lastExpression = -1;
    int lastBrightness = -1;
};
