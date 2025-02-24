using System;

public interface IInitializable
{
    bool IsInitialized { get; }
    void Initialize();
}