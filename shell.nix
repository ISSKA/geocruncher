{ nixpkgs ? (import <nixpkgs> {}), gmlib ? (nixpkgs.callPackage ../viskar-ops/packages/gmlib.nix {}) }:

with nixpkgs;

(python36.withPackages (ps: with ps; [ numpy pytest gmlib ])).env
