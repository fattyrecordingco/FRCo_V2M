#pragma once

#include "PluginProcessor.h"

class VINSPluginAudioProcessorEditor final : public juce::AudioProcessorEditor
{
public:
    explicit VINSPluginAudioProcessorEditor(VINSPluginAudioProcessor&);
    ~VINSPluginAudioProcessorEditor() override;

    void paint(juce::Graphics&) override;
    void resized() override;

private:
    VINSPluginAudioProcessor& processor;
    juce::Label titleLabel;
    juce::Label bodyLabel;
};

