#include "PluginProcessor.h"
#include "PluginEditor.h"

namespace
{
juce::AudioProcessorValueTreeState::ParameterLayout makeLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;
    params.push_back(std::make_unique<juce::AudioParameterFloat>("mix", "Mix", 0.0f, 1.0f, 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterBool>("passthrough", "Passthrough", true));
    return { params.begin(), params.end() };
}
} // namespace

VINSPluginAudioProcessor::VINSPluginAudioProcessor()
    : AudioProcessor(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      parameters(*this, nullptr, "PARAMETERS", makeLayout())
{
}

VINSPluginAudioProcessor::~VINSPluginAudioProcessor() = default;

void VINSPluginAudioProcessor::prepareToPlay(double, int) {}

void VINSPluginAudioProcessor::releaseResources() {}

bool VINSPluginAudioProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet();
}

void VINSPluginAudioProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals noDenormals;
    const auto* mixParam = parameters.getRawParameterValue("mix");
    const auto* passParam = parameters.getRawParameterValue("passthrough");
    const float mix = mixParam != nullptr ? mixParam->load() : 1.0f;
    const bool passthrough = passParam != nullptr ? passParam->load() > 0.5f : true;

    if (!passthrough)
    {
        buffer.clear();
        return;
    }

    if (mix < 0.999f)
    {
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
        {
            buffer.applyGain(channel, 0, buffer.getNumSamples(), mix);
        }
    }
}

juce::AudioProcessorEditor* VINSPluginAudioProcessor::createEditor()
{
    return new VINSPluginAudioProcessorEditor(*this);
}

void VINSPluginAudioProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    if (auto xml = parameters.state.createXml())
    {
        copyXmlToBinary(*xml, destData);
    }
}

void VINSPluginAudioProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    if (auto xml = getXmlFromBinary(data, sizeInBytes))
    {
        parameters.state = juce::ValueTree::fromXml(*xml);
    }
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new VINSPluginAudioProcessor();
}

