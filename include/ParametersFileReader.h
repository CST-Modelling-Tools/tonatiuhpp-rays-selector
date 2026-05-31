#ifndef PARAMETERSFILEREADER_H
#define PARAMETERSFILEREADER_H

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <unordered_map>
#include <vector>

class ParametersFileReader
{
public:
    explicit ParametersFileReader(std::string folderPath, std::string parametersFileName = "");

    void read();

    const std::unordered_map<std::uint64_t, std::string>& getSurfaceMap() const;
    double getPowerPerPhoton() const;
    const std::filesystem::path& getParametersFilePath() const { return m_parametersFilePath; }
    const std::string& getPhotonFilePrefix() const { return m_photonFilePrefix; }

private:
    std::filesystem::path findParametersFile() const;
    static std::string inferPhotonFilePrefix(const std::filesystem::path& parametersFilePath);

    void parseParameterBlock(std::ifstream& file);
    void parseSurfaceBlock(std::ifstream& file);
    void parsePowerAfterSurfaces(std::ifstream& file);

    static bool matchesExpectedParameterList(const std::vector<std::string>& actual);
    static std::string trim(const std::string& s);
    static std::string normalizeId(const std::string& s);

    std::filesystem::path m_folderPath;
    std::string m_parametersFileName;
    std::filesystem::path m_parametersFilePath;
    std::string m_photonFilePrefix;
    std::unordered_map<std::uint64_t, std::string> m_surfaceMap;
    double m_powerPerPhoton = 0.0;
};

#endif // PARAMETERSFILEREADER_H
